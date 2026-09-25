from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from test_store import result, source

from brief.db import require_row
from brief.model import Completion, ModelError
from brief.worker import run_once

if TYPE_CHECKING:
    from brief.contracts import GenerationInput
    from brief.crawl.runner import CrawlResult
    from brief.store import Store


pytestmark = pytest.mark.integration


class Generator:
    def generate(self, context: GenerationInput) -> Completion:
        return Completion(
            raw={
                "guide": {
                    "title": "Example",
                    "summary": {"text": "Example site", "evidenceIds": [context.sources[0].id]},
                    "context": [],
                    "sections": [
                        {
                            "title": "Resources",
                            "links": [{"sourceId": context.sources[0].id, "label": "Home", "description": None}],
                        }
                    ],
                },
                "explanation": "Generated from the saved source.",
                "questions": [],
            },
            metadata={"provider": "fixture", "model": "test"},
        )


async def test_crawl_enqueues_generation_and_model_failure_does_not_recrawl(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")
    calls = []

    async def crawler(*args: Any) -> CrawlResult:
        calls.append("crawl")
        return result(source())

    class FailsOnce(Generator):
        attempts = 0

        def generate(self, context: GenerationInput) -> Completion:
            self.attempts += 1
            if self.attempts == 1:
                raise ModelError("Temporary provider failure", retryable=True)
            return super().generate(context)

    generator = FailsOnce()
    await run_once(store, crawler=crawler, generator=generator)
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["jobs"][0]["kind"] == "generate"
    assert state["draft"] is None
    await run_once(store, crawler=crawler, generator=generator)
    assert require_row(store.get_project(project["id"], token))["jobs"][0]["status"] == "pending"
    with store.db.connect() as connection:
        connection.execute("UPDATE jobs SET available_at = now() WHERE kind = 'generate'")
    await run_once(store, crawler=crawler, generator=generator)
    state = store.get_project(project["id"], token)
    assert calls == ["crawl"]
    assert state is not None
    assert state["draft"]["markdown"].startswith("# Example")
    assert state["draft"]["snapshot_id"] == state["latest_snapshot_id"]
    assert state["draft"]["generation_input"]["decisions"] == []


async def test_refresh_saves_proposal_without_overwriting_draft(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")
    content = "Initial version"

    async def crawler(*args: Any) -> CrawlResult:
        return result(source(content=content))

    generator = Generator()
    await run_once(store, crawler=crawler, generator=generator)
    await run_once(store, generator=generator)
    first = require_row(store.get_project(project["id"], token))["draft_version_id"]
    content = "A changed page"
    store.enqueue_refresh(project["id"], "changed")
    await run_once(store, crawler=crawler, generator=generator)
    await run_once(store, generator=generator)
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["draft_version_id"] == first
    assert state["proposal"]["kind"] == "proposal"
    assert state["proposal"]["snapshot_id"] == state["latest_snapshot_id"]
    # Unchanged checks do not spend another model call.
    store.enqueue_refresh(project["id"], "unchanged")
    await run_once(store, crawler=crawler, generator=generator)
    assert not await run_once(store, generator=generator)


async def test_nonretriable_model_error_is_terminal_and_preserves_snapshot(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")
    store.finish_crawl(require_row(store.claim()), result(source()), enqueue_generation=True)

    class Broken:
        def generate(self, context: GenerationInput) -> Completion:
            raise ModelError("OpenAI request failed (HTTP 401)")

    await run_once(store, generator=Broken())
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["jobs"][0]["status"] == "failed"
    assert state["snapshot"] is not None
    assert state["draft"] is None


def test_stale_generation_cannot_replace_draft(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")
    store.finish_crawl(require_row(store.claim()), result(source()), enqueue_generation=True)
    job = store.claim()
    assert job is not None
    context = store.generation_context(job)
    with store.db.connect() as connection:
        connection.execute("UPDATE projects SET revision = revision + 1 WHERE id = %s", (project["id"],))
    assert store.finish_generation(job, context, Generator().generate(context))["status"] == "superseded"
    assert require_row(store.get_project(project["id"], token))["draft"] is None


def test_refresh_input_pins_draft_and_precise_changes_without_old_decisions(store: Store) -> None:
    import json

    from test_editor import setup_project

    from brief.editor import input_snapshot
    from brief.generation import build_request

    project, _token = setup_project(store)
    baseline = project["draft"]["markdown"]
    store.enqueue_refresh(project["id"], "two-new-pages")
    store.finish_crawl(
        require_row(store.claim()),
        result(
            source(),
            source("https://example.com/a").model_copy(update={"id": "new-a"}),
            source("https://example.com/b").model_copy(update={"id": "new-b"}),
        ),
        enqueue_generation=True,
    )
    job = store.claim()
    assert job is not None
    context = store.generation_context(job)
    assert context.refresh_baseline is not None
    assert context.refresh_baseline.markdown == baseline
    assert context.refresh_baseline.added_source_ids == ["new-a", "new-b"]
    assert context.refresh_baseline.changed_source_ids == []
    assert context.refresh_baseline.removed_source_ids == []
    request = build_request(context)
    assert json.loads(request["user"])["refreshBaseline"]["markdown"] == baseline
    with store.db.connect() as c:
        current = c.execute("SELECT * FROM projects WHERE id=%s", (project["id"],)).fetchone()
        assert current is not None
        current["decisions_revision"] += 1
        assert input_snapshot(c, current, job["snapshot_id"]).refresh_baseline is None
        current["decisions_revision"] -= 1
        assert input_snapshot(c, current, job["snapshot_id"], mode="questions").refresh_baseline is None
    saved_baseline = store.generation_context(job).refresh_baseline
    assert saved_baseline is not None
    assert saved_baseline.markdown == baseline
