from __future__ import annotations

import hashlib
import secrets
from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from brief.contracts import GenerationInput, Source, validate_result
from brief.crawl.fetch import normalize_url
from brief.crawl.runner import CrawlResult, Scope
from brief.db import Database, require_row
from brief.editor import input_snapshot
from brief.generation import render_guide
from brief.refresh import StoredPage, reconcile_pages

if TYPE_CHECKING:
    from brief.model import Completion


class LeaseLost(RuntimeError):
    pass


class Store:
    def __init__(self, database: Database) -> None:
        self.db = database

    def create_project(self, site_url: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
        site_url = normalize_url(site_url)
        token = secrets.token_urlsafe(32)
        project_id = uuid4()
        with self.db.connect() as connection:
            origin = Scope(site_url).origin + "/"
            guide_path = Scope(site_url).path.rstrip("/") + "/"
            connection.execute("INSERT INTO sites(id,url) VALUES (%s,%s)", (project_id, origin))
            project = connection.execute(
                "INSERT INTO projects(id,site_id,site_url,guide_path,management_token_hash) VALUES (%s,%s,%s,%s,%s) RETURNING *",
                (project_id, project_id, site_url, guide_path, hashlib.sha256(token.encode()).hexdigest()),
            ).fetchone()
            assert project is not None
            job = self._enqueue(connection, project, f"initial:{project_id}", "initial_crawl")
        project.pop("management_token_hash")
        return project, token, job

    def get_project(self, project_id: UUID, token: str, *, guide_path: str | None = None) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            if guide_path is None:
                project = connection.execute("SELECT * FROM projects WHERE id = %s", (project_id,)).fetchone()
            else:
                project = connection.execute(
                    "SELECT * FROM projects WHERE site_id = %s AND guide_path = %s", (project_id, guide_path)
                ).fetchone()
            if not project or not secrets.compare_digest(
                project["management_token_hash"], hashlib.sha256(token.encode()).hexdigest()
            ):
                return None
            project_id = project["id"]
            project.pop("management_token_hash")
            from brief.guide_tests import list_runs

            project["test_runs"] = list_runs(connection, project_id)
            project["jobs"] = connection.execute(
                "SELECT id, kind, status, attempt, error, result, progress, created_at, completed_at FROM jobs WHERE project_id = %s ORDER BY created_at DESC LIMIT 10",
                (project_id,),
            ).fetchall()
            for job in project["jobs"]:
                result = job.get("result") or {}
                if job["status"] == "failed" and "warnings" not in result:
                    snapshot = connection.execute(
                        "SELECT warnings FROM crawl_snapshots WHERE project_id = %s AND job_id = %s ORDER BY attempt DESC LIMIT 1",
                        (project_id, job["id"]),
                    ).fetchone()
                    if snapshot:
                        job["result"] = {**result, "warnings": snapshot["warnings"]}
            project["snapshot"] = connection.execute(
                "SELECT * FROM crawl_snapshots WHERE id = %s", (project["latest_snapshot_id"],)
            ).fetchone()
            project["draft"] = connection.execute(
                "SELECT * FROM document_versions WHERE id = %s", (project["draft_version_id"],)
            ).fetchone()
            project["proposal"] = connection.execute(
                "SELECT * FROM document_versions WHERE id = %s", (project["proposal_version_id"],)
            ).fetchone()
            project["decisions"] = connection.execute(
                "SELECT * FROM decisions WHERE project_id = %s ORDER BY created_at", (project_id,)
            ).fetchall()
            project["questions"] = connection.execute(
                "SELECT * FROM questions WHERE project_id = %s ORDER BY created_at", (project_id,)
            ).fetchall()
            project["versions"] = connection.execute(
                "SELECT id, kind, manually_edited, created_at FROM document_versions WHERE project_id = %s ORDER BY created_at DESC LIMIT 30",
                (project_id,),
            ).fetchall()
            project["guides"] = connection.execute(
                """SELECT p.id,p.guide_path,p.guide_name,p.guide_purpose,p.auto_reason,p.auto_cancelled,p.draft_version_id,
                (SELECT status FROM jobs WHERE project_id=p.id ORDER BY created_at DESC LIMIT 1) AS status,
                (SELECT count(*) FROM decisions WHERE project_id=p.id AND active AND needs_review) AS reviews
                FROM projects p WHERE site_id=%s ORDER BY guide_path""",
                (project["site_id"],),
            ).fetchall()
            from brief.guides import suggestions

            project["guide_suggestions"] = suggestions(
                project["snapshot"]["sources"] if project["snapshot"] else [], project["guides"]
            )
            from brief.change_inbox import build

            project["change_inbox"] = build(project)
            from difflib import unified_diff

            project["proposal_diff"] = (
                "\n".join(
                    unified_diff(
                        (project["draft"]["markdown"] if project["draft"] else "").splitlines(),
                        (project["proposal"]["markdown"] if project["proposal"] else "").splitlines(),
                        fromfile="Current draft",
                        tofile="Proposed update",
                        lineterm="",
                    )
                )
                if project["proposal"]
                else None
            )
            return project

    @staticmethod
    def _enqueue(
        connection: Connection[dict[str, Any]],
        project: dict[str, Any],
        key: str,
        kind: str = "refresh",
        snapshot_id: UUID | None = None,
    ) -> dict[str, Any]:
        # Called while holding the project lock (or in the project-creation transaction).
        active = connection.execute(
            "SELECT * FROM jobs WHERE project_id = %s AND status IN ('pending', 'running')", (project["id"],)
        ).fetchone()
        if active:
            return active
        existing = connection.execute("SELECT * FROM jobs WHERE idempotency_key = %s", (key,)).fetchone()
        if existing:
            return existing
        context = None
        if kind == "generate":
            if snapshot_id is None:
                raise ValueError("Generation jobs require a snapshot")
            context = input_snapshot(connection, project, snapshot_id).model_dump()
        return require_row(
            connection.execute(
                "INSERT INTO jobs(id, project_id, kind, idempotency_key, expected_revision, snapshot_id, generation_input) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (uuid4(), project["id"], kind, key, project["revision"], snapshot_id, Jsonb(context)),
            ).fetchone()
        )

    def enqueue_refresh(self, project_id: UUID, request_key: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            project = connection.execute("SELECT * FROM projects WHERE id = %s FOR UPDATE", (project_id,)).fetchone()
            if not project:
                raise KeyError("Project not found")
            return self._enqueue(connection, project, f"manual:{project_id}:{request_key}")

    def set_monitoring(self, project_id: UUID, enabled: bool) -> None:
        with self.db.connect() as connection:
            connection.execute("UPDATE projects SET monitor_enabled = %s WHERE id = %s", (enabled, project_id))

    def schedule_due(self, limit: int = 100) -> int:
        count = 0
        with self.db.connect() as connection:
            projects = connection.execute(
                "SELECT * FROM projects WHERE monitor_enabled AND next_check_at <= now() ORDER BY next_check_at LIMIT %s FOR UPDATE SKIP LOCKED",
                (limit,),
            ).fetchall()
            for project in projects:
                job = self._enqueue(
                    connection, project, f"scheduled:{project['id']}:{project['next_check_at'].isoformat()}"
                )
                if job["kind"] == "refresh":
                    count += 1
                connection.execute(
                    "UPDATE projects SET next_check_at = now() + interval '1 day' WHERE id = %s", (project["id"],)
                )
        return count

    def claim(self, lease_seconds: int = 180) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            # Exhausted crashed jobs must not permanently occupy the project's active slot.
            connection.execute(
                """UPDATE jobs SET status = 'failed', error = 'Worker lease expired; retry limit reached',
                    completed_at = now(), lease_token = NULL, lease_expires_at = NULL
                    WHERE status = 'running' AND lease_expires_at <= now() AND attempt >= max_attempts"""
            )
            job = connection.execute(
                """SELECT * FROM jobs WHERE attempt < max_attempts AND
                    ((status = 'pending' AND available_at <= now()) OR (status = 'running' AND lease_expires_at <= now()))
                    ORDER BY available_at, created_at LIMIT 1 FOR UPDATE SKIP LOCKED"""
            ).fetchone()
            if not job:
                return None
            return connection.execute(
                """UPDATE jobs SET status = 'running', attempt = attempt + 1, lease_token = %s,
                    lease_expires_at = now() + make_interval(secs => %s), error = NULL
                    WHERE id = %s RETURNING *""",
                (uuid4(), lease_seconds, job["id"]),
            ).fetchone()

    def renew(self, job: dict[str, Any], lease_seconds: int = 180) -> bool:
        with self.db.connect() as connection:
            return (
                connection.execute(
                    """UPDATE jobs SET lease_expires_at = now() + make_interval(secs => %s)
                    WHERE id = %s AND status = 'running' AND lease_token = %s AND lease_expires_at > clock_timestamp()""",
                    (lease_seconds, job["id"], job["lease_token"]),
                ).rowcount
                == 1
            )

    def crawl_context(self, job: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        with self.db.connect() as connection:
            project = connection.execute("SELECT * FROM projects WHERE id = %s", (job["project_id"],)).fetchone()
            assert project is not None
            snapshot = connection.execute(
                "SELECT * FROM crawl_snapshots WHERE id = %s", (project["latest_snapshot_id"],)
            ).fetchone()
        return project, snapshot

    @staticmethod
    def _lock_live_job(connection: Connection[dict[str, Any]], job: dict[str, Any]) -> dict[str, Any]:
        live = connection.execute(
            "SELECT * FROM jobs WHERE id = %s AND status = 'running' AND lease_token = %s AND lease_expires_at > clock_timestamp() FOR UPDATE",
            (job["id"], job["lease_token"]),
        ).fetchone()
        if not live:
            raise LeaseLost("Worker no longer owns the job")
        return live

    def report_progress(self, job: dict[str, Any], progress: dict[str, Any]) -> None:
        with self.db.connect() as connection:
            self._lock_live_job(connection, job)
            connection.execute("UPDATE jobs SET progress=%s WHERE id=%s", (Jsonb(progress), job["id"]))

    def finish_crawl(
        self, job: dict[str, Any], result: CrawlResult, *, enqueue_generation: bool = False
    ) -> dict[str, Any]:
        with self.db.connect() as connection:
            # Project-before-job lock order matches enqueue and future publication writes.
            project = connection.execute(
                "SELECT * FROM projects WHERE id = %s FOR UPDATE", (job["project_id"],)
            ).fetchone()
            live = self._lock_live_job(connection, job)
            assert project is not None
            if project["revision"] != live["expected_revision"]:
                connection.execute(
                    "UPDATE jobs SET status = 'superseded', completed_at = now(), lease_token = NULL, lease_expires_at = NULL WHERE id = %s",
                    (job["id"],),
                )
                return {"status": "superseded"}
            old = connection.execute(
                "SELECT * FROM crawl_snapshots WHERE id = %s", (project["latest_snapshot_id"],)
            ).fetchone()
            if result.discovery_state is not None:
                from brief.crawl.inventory import save

                save(connection, project["id"], result.discovery_state)
            reconciled = reconcile_pages(
                [StoredPage(**p) for p in old["page_state"]] if old else [], result.observations
            )
            sources = {s["url"]: s for s in old["sources"]} if old else {}
            sources.update({s.url: s.model_dump() for s in result.sources})
            for removed in reconciled["removed"]:
                sources.pop(removed, None)
            usable = bool(result.sources)
            status = (
                "failed"
                if not usable
                else "partial"
                if result.truncated or result.warnings or reconciled["unavailable"]
                else "complete"
            )
            snapshot_id = uuid4()
            changes = {key: reconciled[key] for key in ["added", "modified", "removed", "unavailable", "changed"]}
            coverage: dict[str, Any] = {
                "sitemap_discovery": result.sitemap_discovery,
                "duration_ms": result.duration_ms,
                "cache_hits": result.cache_hits,
                "conditional_requests": result.conditional_requests,
                "trace": result.trace,
                "stop_reason": result.stop_reason,
                "downloaded_bytes": result.downloaded_bytes,
                "assessment": result.assessment,
                "unread": result.unread,
                "attempted": result.attempted,
                "discovered": result.discovered,
                "truncated": result.truncated,
                "fresh_sources": len(result.sources),
                "retained_sources": len(sources) - len(result.sources),
            }
            connection.execute(
                """INSERT INTO crawl_snapshots(id, project_id, job_id, attempt, status, extraction_version,
                    sources, page_state, observations, changes, coverage, warnings)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    snapshot_id,
                    project["id"],
                    job["id"],
                    live["attempt"],
                    status,
                    result.extraction_version,
                    Jsonb(list(sources.values())),
                    Jsonb([asdict(p) for p in reconciled["pages"]]),
                    Jsonb([asdict(o) for o in result.observations]),
                    Jsonb(changes),
                    Jsonb(coverage),
                    Jsonb(result.warnings),
                ),
            )
            summary: dict[str, Any] = {
                "snapshot_id": str(snapshot_id),
                "status": status,
                "changes": changes,
                "coverage": coverage,
                "warnings": result.warnings,
            }
            connection.execute(
                "UPDATE projects SET last_checked_at = now(), last_check_status = %s WHERE id = %s",
                (status, project["id"]),
            )
            if usable:
                from brief.decision_review import mark_changed_decisions

                mark_changed_decisions(connection, project["id"], list(sources.values()))
                connection.execute(
                    "UPDATE projects SET latest_snapshot_id = %s, revision = revision + 1 WHERE id = %s",
                    (snapshot_id, project["id"]),
                )
                connection.execute(
                    "UPDATE jobs SET status = 'succeeded', result = %s, completed_at = now(), lease_token = NULL, lease_expires_at = NULL WHERE id = %s",
                    (Jsonb(summary), job["id"]),
                )
                if enqueue_generation and (changes["changed"] or not project["draft_version_id"]):
                    project["revision"] += 1
                    generation_job = self._enqueue(
                        connection, project, f"generate:{snapshot_id}", "generate", snapshot_id
                    )
                    summary["generation_job_id"] = str(generation_job["id"])
                    connection.execute("UPDATE jobs SET result = %s WHERE id = %s", (Jsonb(summary), job["id"]))
            else:
                self._fail(connection, live, "No usable source pages; inspect crawl warnings", summary)
            return summary

    @staticmethod
    def _fail(
        connection: Connection[dict[str, Any]],
        live: dict[str, Any],
        error: str,
        result: dict[str, Any] | None = None,
        *,
        retryable: bool = True,
    ) -> None:
        retry = retryable and live["attempt"] < live["max_attempts"]
        connection.execute(
            """UPDATE jobs SET status = %s, error = %s, result = %s, progress = %s,
                available_at = now() + make_interval(secs => %s),
                completed_at = CASE WHEN %s THEN NULL ELSE now() END, lease_token = NULL, lease_expires_at = NULL
                WHERE id = %s""",
            (
                "pending" if retry else "failed",
                error[:500],
                Jsonb(result),
                Jsonb(
                    {
                        "stage": "waiting" if retry else "failed",
                        "message": "The last attempt could not finish. Waiting to retry…"
                        if retry
                        else "The update could not finish. You can retry it.",
                    }
                ),
                min(300, 5 * 2 ** live["attempt"]),
                retry,
                live["id"],
            ),
        )

    def fail(self, job: dict[str, Any], error: str, *, retryable: bool = True) -> None:
        with self.db.connect() as connection:
            live = self._lock_live_job(connection, job)
            self._fail(connection, live, error, retryable=retryable)

    def enqueue_generation(self, project_id: UUID, request_key: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            project = connection.execute("SELECT * FROM projects WHERE id = %s FOR UPDATE", (project_id,)).fetchone()
            if not project or not project["latest_snapshot_id"]:
                raise ValueError("A usable source snapshot is required before generation")
            job = self._enqueue(
                connection,
                project,
                f"generate-manual:{project_id}:{request_key}",
                "generate",
                project["latest_snapshot_id"],
            )

            draft = connection.execute(
                "SELECT decisions_revision, snapshot_id FROM document_versions WHERE id = %s",
                (project["draft_version_id"],),
            ).fetchone()
            if (
                job["kind"] == "generate"
                and draft
                and draft["decisions_revision"] != project["decisions_revision"]
                and draft["snapshot_id"] == project["latest_snapshot_id"]
            ):
                connection.execute("UPDATE jobs SET replace_draft = true WHERE id = %s", (job["id"],))
            return job

    def generation_context(self, job: dict[str, Any]) -> GenerationInput:
        if job.get("generation_input"):
            return GenerationInput.model_validate(job["generation_input"])
        with self.db.connect() as connection:
            project = connection.execute("SELECT * FROM projects WHERE id = %s", (job["project_id"],)).fetchone()
            snapshot = connection.execute(
                "SELECT * FROM crawl_snapshots WHERE id = %s AND project_id = %s",
                (job["snapshot_id"], job["project_id"]),
            ).fetchone()
        if not snapshot or not snapshot["sources"]:
            raise ValueError("Generation requires a usable pinned source snapshot")
        # Decision editing is the next slice; do not infer saved decisions from chat.
        assert project is not None
        return GenerationInput(
            site_url=project["site_url"],
            sources=[Source.model_validate(s) for s in snapshot["sources"]],
            decisions=[],
            dismissed_topics=[],
            mode="generate",
            max_questions=3,
        )

    def finish_generation(
        self, job: dict[str, Any], context: GenerationInput, completion: Completion
    ) -> dict[str, Any]:
        result = validate_result(completion.raw, context)
        markdown = render_guide(result.guide, context.sources) if result.guide else None
        with self.db.connect() as connection:
            project = connection.execute(
                "SELECT * FROM projects WHERE id = %s FOR UPDATE", (job["project_id"],)
            ).fetchone()
            live = self._lock_live_job(connection, job)
            assert project is not None
            if project["revision"] != live["expected_revision"] or project["latest_snapshot_id"] != live["snapshot_id"]:
                connection.execute(
                    "UPDATE jobs SET status = 'superseded', completed_at = now(), lease_token = NULL, lease_expires_at = NULL WHERE id = %s",
                    (job["id"],),
                )
                return {"status": "superseded"}
            for question in result.questions:
                connection.execute(
                    "INSERT INTO questions(id,project_id,snapshot_id,topic,data) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (uuid4(), project["id"], live["snapshot_id"], question.topic, Jsonb(question.model_dump())),
                )
            if context.mode == "questions":
                summary: dict[str, Any] = {
                    "status": "succeeded",
                    "explanation": result.explanation,
                    "question_count": len(result.questions),
                }
                connection.execute(
                    "UPDATE jobs SET status = 'succeeded', result = %s, completed_at = now(), lease_token = NULL, lease_expires_at = NULL WHERE id = %s",
                    (Jsonb(summary), job["id"]),
                )
                connection.execute("UPDATE projects SET revision = revision + 1 WHERE id = %s", (project["id"],))
                return summary
            from brief.guides import link_ready_child, linked_markdown, plan_automatic

            assert markdown is not None
            markdown = linked_markdown(connection, project, markdown)
            version_id = uuid4()
            kind = "draft" if live["replace_draft"] or not project["draft_version_id"] else "proposal"
            connection.execute(
                """INSERT INTO document_versions(id, project_id, job_id, snapshot_id, kind, generation_input,
                    structured_result, markdown, model_metadata, decisions_revision) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    version_id,
                    project["id"],
                    job["id"],
                    live["snapshot_id"],
                    kind,
                    Jsonb(context.model_dump()),
                    Jsonb(result.model_dump()),
                    markdown,
                    Jsonb(completion.metadata),
                    project["decisions_revision"],
                ),
            )
            if kind == "draft":
                connection.execute(
                    "UPDATE projects SET draft_version_id = %s, proposal_version_id = NULL, revision = revision + 1 WHERE id = %s",
                    (version_id, project["id"]),
                )
            else:
                connection.execute(
                    "UPDATE projects SET proposal_version_id = %s, revision = revision + 1 WHERE id = %s",
                    (version_id, project["id"]),
                )
            plan_automatic(self, connection, project, [s.model_dump() for s in context.sources])
            link_ready_child(connection, project)
            summary = {"status": "succeeded", "version_id": str(version_id), "kind": kind}
            connection.execute(
                "UPDATE jobs SET status = 'succeeded', result = %s, completed_at = now(), lease_token = NULL, lease_expires_at = NULL WHERE id = %s",
                (Jsonb(summary), job["id"]),
            )
            return summary
