from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest
from psycopg.types.json import Jsonb
from test_editor import finish, setup_project
from test_generation_jobs import Generator
from test_store import result, source

from brief import editor
from brief.contracts import validate_result
from brief.crawl.runner import CrawlResult
from brief.db import require_row
from brief.refresh import Observation

if TYPE_CHECKING:
    from brief.store import Store


pytestmark = pytest.mark.integration


def answer(store: Store) -> tuple[dict[str, Any], str]:
    project, token = setup_project(store)
    question_id = uuid4()
    with store.db.connect() as connection:
        connection.execute(
            "INSERT INTO questions(id,project_id,snapshot_id,topic,data) VALUES (%s,%s,%s,%s,%s)",
            (
                question_id,
                project["id"],
                project["latest_snapshot_id"],
                "shipping",
                Jsonb({"question": "Which shipping threshold applies?", "evidence_ids": ["root"]}),
            ),
        )
    editor.save_decision(
        store,
        project["id"],
        project["revision"],
        statement="€450 until the website is corrected",
        kind="fact",
        question_id=question_id,
    )
    finish(store)
    return require_row(store.get_project(project["id"], token)), token


def refresh(store: Store, pid: UUID, output: CrawlResult, key: str) -> None:
    store.enqueue_refresh(pid, key)
    store.finish_crawl(require_row(store.claim()), output, enqueue_generation=True)


def test_changed_answer_reopens_with_old_evidence_and_cannot_establish_claim(store: Store) -> None:
    project, token = answer(store)
    pid = project["id"]
    refresh(store, pid, result(source(content="Free delivery now applies above €600, effective today.")), "changed")
    current = store.get_project(pid, token)
    assert current is not None
    assert current["decisions"][0]["needs_review"]
    assert current["draft_version_id"] == project["draft_version_id"]
    job = store.claim()
    assert job is not None
    context = store.generation_context(job)
    assert "shipping" not in context.dismissed_topics
    decision = context.decisions[0]
    assert decision.needs_review and decision.review_sources[0].content == source().content
    raw = Generator().generate(context).raw
    raw["guide"]["summary"] = {"text": "Free delivery above €450.", "evidenceIds": [decision.id]}
    with pytest.raises(ValueError, match="awaiting review"):
        validate_result(raw, context)
    store.finish_generation(job, context, Generator().generate(context))
    assert require_row(store.get_project(pid, token))["draft_version_id"] == project["draft_version_id"]


@pytest.mark.parametrize("resolution", ["keep", "revise", "remove"])
def test_resolution_rebases_or_removes_same_decision(store: Store, resolution: str) -> None:
    project, token = answer(store)
    pid = project["id"]
    fresh = source(content="The current shipping threshold is €600. This policy has changed.")
    refresh(store, pid, result(fresh), "changed")
    finish(store)
    current = store.get_project(pid, token)
    assert current is not None
    decision = current["decisions"][0]
    statement = "The new threshold is €600" if resolution == "revise" else decision["statement"]
    editor.save_decision(
        store,
        pid,
        current["revision"],
        decision_id=decision["id"],
        statement=statement,
        kind="fact",
        active=resolution != "remove",
    )
    context = finish(store)
    updated = store.get_project(pid, token)
    assert updated is not None
    assert updated["draft_version_id"] == current["draft_version_id"]
    assert updated["proposal"]["decisions_revision"] == updated["decisions_revision"]
    assert updated["change_inbox"]
    editor.use_version(store, pid, updated["revision"], updated["proposal_version_id"])
    assert require_row(store.get_project(pid, token))["change_inbox"] == []
    if resolution == "remove":
        assert context.decisions == []
    else:
        assert len(context.decisions) == 1
        assert not context.decisions[0].needs_review
        assert context.decisions[0].review_sources[0].content == fresh.content
        assert context.decisions[0].statement == statement
        refresh(store, pid, result(fresh), "same-again")
        assert not require_row(store.get_project(pid, token))["decisions"][0]["needs_review"]


def test_unrelated_source_and_unavailable_evidence_do_not_reopen_answer(store: Store) -> None:
    project, token = answer(store)
    pid = project["id"]
    other = source("https://example.com/about", "An unrelated page with changed team information.")
    refresh(store, pid, result(source(), other), "unrelated")
    finish(store)
    assert not require_row(store.get_project(pid, token))["decisions"][0]["needs_review"]
    unavailable = result(other)
    unavailable.observations.append(Observation(source().url, "unavailable"))
    refresh(store, pid, unavailable, "unavailable")
    assert not require_row(store.get_project(pid, token))["decisions"][0]["needs_review"]


def test_editorial_preference_without_question_has_no_source_expiry(store: Store) -> None:
    project, token = setup_project(store)
    editor.save_decision(store, project["id"], project["revision"], statement="Write concisely", kind="preference")
    finish(store)
    refresh(
        store,
        project["id"],
        result(source(content="Entirely new site content with sufficiently long wording.")),
        "changed",
    )
    assert not require_row(store.get_project(project["id"], token))["decisions"][0]["needs_review"]


def test_confirmed_source_removal_reopens_but_first_404_does_not(store: Store) -> None:
    project, token = answer(store)
    pid = project["id"]
    other = source("https://example.com/about", "A second usable source keeps this refresh usable.")
    for attempt in range(2):
        output = result(other)
        output.observations.append(Observation(source().url, "not-found"))
        refresh(store, pid, output, f"missing-{attempt}")
        assert require_row(store.get_project(pid, token))["decisions"][0]["needs_review"] == (attempt == 1)
        finish(store)


def test_proposal_cannot_be_accepted_before_review_and_retry_keeps_draft(store: Store) -> None:
    project, token = answer(store)
    pid = project["id"]
    refresh(store, pid, result(source(content="A changed shipping threshold.")), "guard")
    finish(store)
    current = store.get_project(pid, token)
    with pytest.raises(editor.EditConflict, match="Resolve flagged"):
        assert current is not None
        editor.use_version(store, pid, current["revision"], current["proposal_version_id"])
    assert current is not None
    d = current["decisions"][0]
    assert d is not None
    editor.save_decision(store, pid, current["revision"], decision_id=d["id"], statement=d["statement"], kind="fact")
    job = store.claim()
    assert job is not None
    store.fail(job, "Fixture failure", retryable=False)
    store.enqueue_generation(pid, "retry-review")
    finish(store)
    updated = store.get_project(pid, token)
    assert updated is not None
    assert updated["draft_version_id"] == current["draft_version_id"]
    assert updated["proposal"]["decisions_revision"] == updated["decisions_revision"]
