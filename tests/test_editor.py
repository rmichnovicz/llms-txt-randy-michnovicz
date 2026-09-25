from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from pytest import MonkeyPatch
from test_generation_jobs import Generator
from test_store import result, source

from brief import editor
from brief.api import create_app
from brief.contracts import GenerationInput
from brief.db import require_row
from brief.model import Completion
from brief.store import LeaseLost

if TYPE_CHECKING:
    from brief.store import Store


pytestmark = pytest.mark.integration


def setup_project(store: Store) -> tuple[dict[str, Any], str]:
    project, token, _ = store.create_project("https://example.com/")
    store.finish_crawl(require_row(store.claim()), result(source()), enqueue_generation=True)
    job = store.claim()
    assert job is not None
    context = store.generation_context(job)
    store.finish_generation(job, context, Generator().generate(context))
    return require_row(store.get_project(project["id"], token)), token


def finish(store: Store) -> GenerationInput:
    job = store.claim()
    assert job is not None
    context = store.generation_context(job)
    store.finish_generation(job, context, Generator().generate(context))
    return context


def test_decision_removal_excludes_old_answer_and_invalidates_inflight_job(store: Store) -> None:
    project, token = setup_project(store)
    saved = editor.save_decision(
        store, project["id"], project["revision"], statement="OMIT_PRICING_MARKER", kind="preference"
    )
    old_job = store.claim()
    assert old_job is not None
    old_context = store.generation_context(old_job)
    assert old_context.decisions[0].statement == "OMIT_PRICING_MARKER"
    state = store.get_project(project["id"], token)
    assert state is not None
    editor.save_decision(
        store,
        project["id"],
        state["revision"],
        decision_id=saved["decision_id"],
        statement="OMIT_PRICING_MARKER",
        kind="preference",
        active=False,
    )
    with pytest.raises(LeaseLost):
        store.finish_generation(old_job, old_context, Generator().generate(old_context))
    assert finish(store).decisions == []
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["draft"]["decisions_revision"] == state["decisions_revision"]
    assert state["draft"]["id"] != project["draft"]["id"]
    assert state["decisions"][0]["active"] is False
    with store.db.connect() as connection:
        assert require_row(connection.execute("SELECT count(*) AS n FROM decision_events").fetchone())["n"] == 2


def test_edit_conflicts_do_not_lose_decisions(store: Store) -> None:
    project, _ = setup_project(store)
    editor.save_decision(store, project["id"], project["revision"], statement="Developer audience", kind="preference")
    with pytest.raises(editor.EditConflict):
        editor.save_decision(store, project["id"], project["revision"], statement="Lost edit", kind="fact")


def test_question_only_result_does_not_create_document_version(store: Store) -> None:
    project, token = setup_project(store)
    editor.ask_more(store, project["id"], project["revision"])
    job = store.claim()
    assert job is not None
    context = store.generation_context(job)
    assert context.mode == "questions" and context.max_questions == 1
    store.finish_generation(
        job,
        context,
        Completion({"guide": None, "questions": [], "explanation": "No consequential questions remain."}, {}),
    )
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["draft"]["id"] == project["draft"]["id"]
    assert len(state["versions"]) == 1
    assert state["jobs"][0]["result"]["question_count"] == 0


def add_question(store: Store, project: dict[str, Any]) -> UUID:
    question_id = uuid4()
    with store.db.connect() as connection:
        connection.execute(
            "INSERT INTO questions(id,project_id,snapshot_id,topic,data) VALUES (%s,%s,%s,%s,%s)",
            (
                question_id,
                project["id"],
                project["latest_snapshot_id"],
                "audience",
                Jsonb({"question": "Who is the audience?"}),
            ),
        )
    return question_id


def test_dismiss_keeps_document_and_suppresses_topic(store: Store) -> None:
    project, token = setup_project(store)
    qid = add_question(store, project)
    editor.dismiss_question(store, project["id"], project["revision"], qid)
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["draft"]["id"] == project["draft"]["id"]
    editor.ask_more(store, project["id"], state["revision"])
    assert "audience" in store.generation_context(require_row(store.claim())).dismissed_topics


def test_question_answer_is_saved_with_context_and_can_be_removed(store: Store) -> None:
    project, token = setup_project(store)
    qid = add_question(store, project)
    saved = editor.save_decision(
        store, project["id"], project["revision"], statement="Developers", kind="preference", question_id=qid
    )
    context = finish(store)
    assert "Who is the audience? Answer: Developers" == context.decisions[0].statement
    assert "audience" in context.dismissed_topics
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["questions"][0]["status"] == "answered"
    editor.save_decision(
        store,
        project["id"],
        state["revision"],
        decision_id=saved["decision_id"],
        statement=context.decisions[0].statement,
        kind="preference",
        active=False,
    )
    context = store.generation_context(require_row(store.claim()))
    assert not context.decisions and "audience" not in context.dismissed_topics


def test_manual_revision_restore_and_cross_project_version_access(store: Store) -> None:
    project, token = setup_project(store)
    saved = editor.save_document(store, project["id"], project["revision"], "# Custom\n\nMy manual copy.\n")
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["draft"]["manually_edited"]
    assert len(state["versions"]) == 2
    with pytest.raises(editor.EditConflict):
        editor.save_document(store, project["id"], project["revision"], "# Stale\n")
    editor.use_version(store, project["id"], state["revision"], project["draft"]["id"])
    assert require_row(store.get_project(project["id"], token))["draft"]["id"] == project["draft"]["id"]
    other, _, _ = store.create_project("https://other.example.com/")
    with pytest.raises(editor.EditConflict):
        editor.use_version(store, other["id"], other["revision"], saved["version_id"])


def test_retry_updates_draft_after_failed_decision_generation(store: Store) -> None:
    project, token = setup_project(store)
    editor.save_decision(store, project["id"], project["revision"], statement="Focus on buyers", kind="preference")
    store.fail(require_row(store.claim()), "Provider error", retryable=False)
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["draft"]["decisions_revision"] != state["decisions_revision"]
    store.enqueue_generation(project["id"], "retry")
    finish(store)
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["draft"]["decisions_revision"] == state["decisions_revision"]
    assert state["proposal"] is None


def test_cookie_session_and_mutation_origin_check(store: Store, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("BRIEF_SECURE_COOKIES", "false")
    monkeypatch.setenv("FRONTEND_ORIGINS", "http://localhost:5173")
    project, token = setup_project(store)
    client = TestClient(create_app(store))
    path = f"/api/projects/{project['id']}"
    response = client.post(path + "/session", json={"token": token}, headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200 and "HttpOnly" in response.headers["set-cookie"]
    assert client.get(path).status_code == 200
    assert client.patch(path + "/monitoring", json={"enabled": True}).status_code == 403
    assert (
        client.patch(path + "/monitoring", json={"enabled": True}, headers={"Origin": "https://evil.test"}).status_code
        == 403
    )
    assert (
        client.patch(
            path + "/monitoring", json={"enabled": True}, headers={"Origin": "http://localhost:5173"}
        ).status_code
        == 200
    )
    assert client.get(path).headers["cache-control"] == "no-store"


@pytest.mark.parametrize("changed_snapshot", [False, True])
def test_restoring_answer_only_resolves_repeated_card_from_same_snapshot(store: Store, changed_snapshot: bool) -> None:
    project, token = setup_project(store)
    qid = add_question(store, project)
    saved = editor.save_decision(
        store, project["id"], project["revision"], statement="Developers", kind="preference", question_id=qid
    )
    finish(store)
    state = store.get_project(project["id"], token)
    assert state is not None
    editor.save_decision(
        store,
        project["id"],
        state["revision"],
        statement="Developers",
        kind="preference",
        decision_id=saved["decision_id"],
        active=False,
    )
    finish(store)
    if changed_snapshot:
        store.enqueue_refresh(project["id"], "new-evidence")
        store.finish_crawl(require_row(store.claim()), result(source()))
    state = store.get_project(project["id"], token)
    assert state is not None
    repeated = add_question(store, state)
    editor.save_decision(
        store,
        project["id"],
        state["revision"],
        statement="Developers",
        kind="preference",
        decision_id=saved["decision_id"],
        active=True,
    )
    state = store.get_project(project["id"], token)
    assert state is not None
    question = next(q for q in state["questions"] if q["id"] == repeated)
    assert question["status"] == ("pending" if changed_snapshot else "answered")
