"""Editor operations share the store's project lock and revision guard."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from brief.contracts import Decision, GenerationInput, RefreshBaseline, Source

if TYPE_CHECKING:
    from brief.store import Store


class EditConflict(ValueError):
    pass


def locked_project(connection: Connection[dict[str, Any]], project_id: UUID, revision: int) -> dict[str, Any]:
    project = connection.execute("SELECT * FROM projects WHERE id = %s FOR UPDATE", (project_id,)).fetchone()
    if not project or project["revision"] != revision:
        raise EditConflict("This project changed. Reload it before saving.")
    return project


def input_snapshot(
    connection: Connection[dict[str, Any]],
    project: dict[str, Any],
    snapshot_id: UUID,
    mode: Literal["generate", "questions"] = "generate",
) -> GenerationInput:
    snapshot = connection.execute(
        "SELECT sources FROM crawl_snapshots WHERE id = %s AND project_id = %s", (snapshot_id, project["id"])
    ).fetchone()
    if not snapshot or not snapshot["sources"]:
        raise EditConflict("Wait for a usable source snapshot first.")
    decisions = connection.execute(
        """SELECT id, kind, statement, active, needs_review,
        evidence_basis AS review_sources FROM decisions WHERE project_id = %s AND active ORDER BY created_at""",
        (project["id"],),
    ).fetchall()
    topics = connection.execute(
        """SELECT q.topic FROM questions q LEFT JOIN decisions d ON d.id = q.decision_id
        WHERE q.project_id = %s AND (q.status = 'pending' OR (q.status = 'dismissed' AND q.snapshot_id = %s)
        OR (q.status = 'answered' AND d.active AND NOT d.needs_review))""",
        (project["id"], snapshot_id),
    ).fetchall()
    if project.get("guide_purpose"):
        decisions.append(
            {
                "id": "guide_purpose",
                "kind": "preference",
                "statement": project["guide_purpose"],
                "active": True,
                "needs_review": False,
                "review_sources": [],
            }
        )
    baseline = None
    if mode == "generate" and project.get("draft_version_id"):
        draft = connection.execute(
            "SELECT markdown,generation_input,snapshot_id,decisions_revision FROM document_versions WHERE id=%s AND project_id=%s",
            (project["draft_version_id"], project["id"]),
        ).fetchone()
        # Never resurrect a removed answer through an old draft. Direction edits
        # regenerate from current authority; source-only refreshes preserve wording.
        if (
            draft
            and draft["snapshot_id"] != snapshot_id
            and draft["decisions_revision"] == project["decisions_revision"]
        ):
            old = {s["id"]: Source.model_validate(s) for s in draft["generation_input"]["sources"]}
            new = {s["id"]: Source.model_validate(s) for s in snapshot["sources"]}
            baseline = RefreshBaseline(
                markdown=draft["markdown"],
                added_source_ids=sorted(new.keys() - old.keys()),
                changed_source_ids=sorted(k for k in new.keys() & old.keys() if new[k] != old[k]),
                removed_source_ids=sorted(old.keys() - new.keys()),
            )
    return GenerationInput(
        refresh_baseline=baseline,
        site_url=project["site_url"],
        sources=[Source.model_validate(s) for s in snapshot["sources"]],
        decisions=[Decision.model_validate(d) for d in decisions],
        dismissed_topics=[t["topic"] for t in topics],
        mode=mode,
        max_questions=1 if mode == "questions" else 3,
    )


def supersede(connection: Connection[dict[str, Any]], project_id: UUID) -> None:
    connection.execute(
        """UPDATE jobs SET status = 'superseded', completed_at = now(), lease_token = NULL,
        lease_expires_at = NULL WHERE project_id = %s AND status IN ('pending', 'running')""",
        (project_id,),
    )


def save_decision(
    store: Store,
    project_id: UUID,
    revision: int,
    *,
    statement: str,
    kind: str,
    decision_id: str | None = None,
    active: bool = True,
    question_id: UUID | None = None,
) -> dict[str, Any]:
    with store.db.connect() as connection:
        project = locked_project(connection, project_id, revision)
        if not project["latest_snapshot_id"]:
            raise EditConflict("Wait for website reading to finish before adding direction.")
        draft = connection.execute(
            "SELECT snapshot_id FROM document_versions WHERE id=%s", (project["draft_version_id"],)
        ).fetchone()
        reviewing_sources = bool(draft and draft["snapshot_id"] != project["latest_snapshot_id"])
        question = None
        if question_id:
            question = connection.execute(
                "SELECT * FROM questions WHERE id = %s AND project_id = %s AND status = 'pending'",
                (question_id, project_id),
            ).fetchone()
            if not question:
                raise EditConflict("This question is no longer pending.")
            statement = f"{question['data']['question']} Answer: {statement}"
        if decision_id:
            decision = connection.execute(
                """UPDATE decisions SET statement = %s, kind = %s, active = %s,
                revision = revision + 1, updated_at = now() WHERE id = %s AND project_id = %s RETURNING *""",
                (statement, kind, active, decision_id, project_id),
            ).fetchone()
            if not decision:
                raise EditConflict("Decision not found.")
        else:
            decision = connection.execute(
                "INSERT INTO decisions(id,project_id,statement,kind,active) VALUES (%s,%s,%s,%s,%s) RETURNING *",
                ("dec_" + uuid4().hex, project_id, statement, kind, active),
            ).fetchone()
        assert decision is not None
        if active:
            snapshot = connection.execute(
                "SELECT sources FROM crawl_snapshots WHERE id=%s", (project["latest_snapshot_id"],)
            ).fetchone()
            previous_ids = {s["id"] for s in decision["evidence_basis"]}
            evidence_ids = set(question["data"].get("evidence_ids", [])) if question else previous_ids
            assert snapshot is not None
            basis = [s for s in snapshot["sources"] if s["id"] in evidence_ids]
            if not evidence_ids and kind == "fact":
                basis = snapshot["sources"]
            connection.execute(
                "UPDATE decisions SET evidence_basis=%s, basis_snapshot_id=%s, needs_review=false WHERE id=%s",
                (Jsonb(basis), project["latest_snapshot_id"], decision["id"]),
            )
            decision.update(evidence_basis=basis, needs_review=False)
        if decision_id and active:
            # Restoring an answer also resolves a repeated card from the same evidence.
            # A different snapshot may represent a new conflict and must stay reviewable.
            connection.execute(
                """UPDATE questions pending SET status='answered', decision_id=%s
                FROM questions answered WHERE answered.project_id=%s AND answered.decision_id=%s
                AND answered.status='answered' AND pending.project_id=answered.project_id
                AND pending.snapshot_id=answered.snapshot_id AND pending.topic=answered.topic
                AND pending.status='pending'""",
                (decision_id, project_id, decision_id),
            )
        connection.execute(
            "INSERT INTO decision_events(project_id,decision) VALUES (%s,%s)",
            (
                project_id,
                Jsonb(
                    {
                        k: decision[k]
                        for k in ["id", "statement", "kind", "active", "revision", "evidence_basis", "needs_review"]
                    }
                ),
            ),
        )
        if question_id:
            connection.execute(
                "UPDATE questions SET status = 'answered', decision_id = %s WHERE id = %s",
                (decision["id"], question_id),
            )
        updated_project = connection.execute(
            "UPDATE projects SET revision = revision + 1, decisions_revision = decisions_revision + 1 WHERE id = %s RETURNING *",
            (project_id,),
        ).fetchone()
        assert updated_project is not None
        project = updated_project
        supersede(connection, project_id)
        job = store._enqueue(
            connection,
            project,
            f"decision:{project_id}:{project['revision']}",
            "generate",
            project["latest_snapshot_id"],
        )
        connection.execute("UPDATE jobs SET replace_draft = %s WHERE id = %s", (not reviewing_sources, job["id"]))
        return {"job_id": job["id"], "decision_id": decision["id"]}


def dismiss_question(store: Store, project_id: UUID, revision: int, question_id: UUID) -> None:
    with store.db.connect() as connection:
        project = locked_project(connection, project_id, revision)
        changed = connection.execute(
            "UPDATE questions SET status = 'dismissed' WHERE id = %s AND project_id = %s AND status = 'pending'",
            (question_id, project_id),
        ).rowcount
        if not changed:
            raise EditConflict("This question is no longer pending.")
        # A pending model response must not reintroduce a just-dismissed question.
        supersede(connection, project_id)
        connection.execute("UPDATE projects SET revision = revision + 1 WHERE id = %s", (project["id"],))


def ask_more(store: Store, project_id: UUID, revision: int) -> dict[str, Any]:
    with store.db.connect() as connection:
        project = locked_project(connection, project_id, revision)
        if connection.execute(
            "SELECT 1 FROM jobs WHERE project_id = %s AND status IN ('pending','running')", (project_id,)
        ).fetchone():
            raise EditConflict("Wait for the current update to finish.")
        context = input_snapshot(connection, project, project["latest_snapshot_id"], "questions")
        job = store._enqueue(connection, project, f"questions:{uuid4()}", "generate", project["latest_snapshot_id"])
        connection.execute(
            "UPDATE jobs SET generation_input = %s WHERE id = %s", (Jsonb(context.model_dump()), job["id"])
        )
        return {"job_id": job["id"]}


def save_document(store: Store, project_id: UUID, revision: int, markdown: str) -> dict[str, Any]:
    if not markdown.lstrip().startswith("# ") or not markdown.splitlines()[0].strip("# ").strip():
        raise EditConflict("Start the document with a title: # Your site name")
    with store.db.connect() as connection:
        project = locked_project(connection, project_id, revision)
        if not project["draft_version_id"]:
            raise EditConflict("Wait for the first draft before editing.")
        old = connection.execute(
            "SELECT * FROM document_versions WHERE id = %s", (project["draft_version_id"],)
        ).fetchone()
        assert old is not None
        if old["markdown"] == markdown:
            return {"version_id": old["id"]}
        version_id = uuid4()
        connection.execute(
            """INSERT INTO document_versions(id,project_id,snapshot_id,kind,generation_input,structured_result,
            markdown,model_metadata,manually_edited,decisions_revision) VALUES (%s,%s,%s,'draft',%s,%s,%s,%s,true,%s)""",
            (
                version_id,
                project_id,
                old["snapshot_id"],
                Jsonb(old["generation_input"]),
                Jsonb(old["structured_result"]),
                markdown,
                Jsonb({"origin": "manual"}),
                project["decisions_revision"],
            ),
        )
        supersede(connection, project_id)
        connection.execute(
            "UPDATE projects SET draft_version_id = %s, revision = revision + 1 WHERE id = %s", (version_id, project_id)
        )
        from brief.guides import link_ready_child

        link_ready_child(connection, project)
        return {"version_id": version_id}


def use_version(store: Store, project_id: UUID, revision: int, version_id: UUID) -> dict[str, Any]:
    with store.db.connect() as connection:
        project = locked_project(connection, project_id, revision)
        version = connection.execute(
            "SELECT * FROM document_versions WHERE id = %s AND project_id = %s", (version_id, project_id)
        ).fetchone()
        if not version:
            raise EditConflict("Document version not found.")
        if version_id == project["proposal_version_id"] and (
            version["decisions_revision"] != project["decisions_revision"]
            or connection.execute(
                "SELECT 1 FROM decisions WHERE project_id=%s AND active AND needs_review", (project_id,)
            ).fetchone()
        ):
            raise EditConflict("Resolve flagged answers and wait for an updated proposal before accepting.")
        supersede(connection, project_id)
        connection.execute(
            "UPDATE projects SET draft_version_id = %s, proposal_version_id = NULL, revision = revision + 1 WHERE id = %s",
            (version_id, project_id),
        )
        from brief.guides import link_ready_child

        link_ready_child(connection, project)
        return {"version_id": version_id}
