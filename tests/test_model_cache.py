from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pytest import MonkeyPatch
from test_editor import setup_project
from test_model import FakeClient, context

from brief.contracts import Decision, Source
from brief.db import require_row
from brief.generation import build_request
from brief.model import OpenAIGenerator
from brief.model_cache import generate

if TYPE_CHECKING:
    from brief.store import Store


class CountingClient(FakeClient):
    calls = 0

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls += 1
        return super().create(**kwargs)


@pytest.mark.integration
def test_exact_cache_is_private_validated_and_configuration_sensitive(store: Store, monkeypatch: MonkeyPatch) -> None:
    p, _ = setup_project(store)
    other, _ = setup_project(store)
    client = CountingClient()
    model = OpenAIGenerator(client=client, model="fixture")
    ctx = context()
    job = {"project_id": p["id"]}
    a = generate(store, job, model, ctx)
    b = generate(store, job, model, ctx)
    assert client.calls == 1
    assert a.raw == b.raw and b.metadata["cache"]["status"] == "hit"
    assert b.metadata["usage"] is None and b.metadata["attempts"] == 0
    generate(store, {"project_id": other["id"]}, model, ctx)
    assert client.calls == 2
    changed = ctx.model_copy(update={"dismissed_topics": ["audience"]})
    generate(store, job, model, changed)
    assert client.calls == 3
    model.reasoning = "low"
    generate(store, job, model, ctx)
    assert client.calls == 4
    monkeypatch.setenv("BRIEF_MODEL_CACHE", "false")
    generate(store, job, model, ctx)
    assert client.calls == 5


@pytest.mark.integration
def test_expired_corrupt_and_failed_results_are_not_reused(store: Store) -> None:
    p, _ = setup_project(store)
    client = CountingClient()
    model = OpenAIGenerator(client=client, model="fixture")
    job = {"project_id": p["id"]}
    generate(store, job, model, context())
    with store.db.connect() as c:
        c.execute("UPDATE model_cache SET created_at=now()-interval '8 days'")
    generate(store, job, model, context())
    with store.db.connect() as c:
        c.execute("UPDATE model_cache SET payload=%s", (b"corrupt",))
    generate(store, job, model, context())
    assert client.calls == 3
    client.error = RuntimeError("failed")
    model.model = "different"
    with pytest.raises(RuntimeError):
        generate(store, job, model, context())
    with store.db.connect() as c:
        assert require_row(c.execute("SELECT count(*) AS n FROM model_cache").fetchone())["n"] == 1


def test_compaction_preserves_changed_historical_evidence_and_stable_prefix() -> None:
    src = Source(
        id="s", url="https://example.com/", title="Policy", description="Shipping", content="Current policy. " * 500
    )
    old = src.model_copy(update={"content": "Old policy."})
    ctx = context().model_copy(
        update={
            "sources": [src],
            "decisions": [
                Decision(id="d", kind="fact", statement="Owner answer", active=True, review_sources=[src]),
                Decision(
                    id="e", kind="fact", statement="Old answer", active=True, needs_review=True, review_sources=[old]
                ),
            ],
        }
    )
    request = build_request(ctx)
    data = json.loads(request["user"])
    assert data["decisions"][0]["reviewSources"] == []
    assert data["decisions"][0]["reviewSourceIds"] == ["s"]
    assert data["decisions"][1]["reviewSources"][0]["content"] == "Old policy."
    assert len(request["user"]) < len(json.dumps(ctx.model_dump(by_alias=True))) * 0.65
    changed = deepcopy(ctx)
    changed.decisions[0].statement = "Different owner answer"
    other = build_request(changed)["user"]
    assert request["user"].split('"decisions":')[0] == other.split('"decisions":')[0]
    assert ctx.decisions[0].review_sources[0].content == src.content


@pytest.mark.integration
@pytest.mark.parametrize("change", ["model", "output_budget", "evidence", "decision", "prompt"])
def test_cache_invalidates_on_material_request_changes(store: Store, monkeypatch: MonkeyPatch, change: str) -> None:
    import brief.generation

    p, _ = setup_project(store)
    client = CountingClient()
    model = OpenAIGenerator(client=client, model="fixture")
    job = {"project_id": p["id"]}
    ctx = context()
    generate(store, job, model, ctx)
    if change == "model":
        model.model = "other-model"
    elif change == "output_budget":
        model.max_output_tokens = 6000
    elif change == "evidence":
        ctx.sources = [
            Source(
                id="new",
                url="https://example.com/new",
                title="New",
                description="New evidence",
                content="Changed source content.",
            )
        ]
    elif change == "decision":
        ctx.decisions = [Decision(id="new", kind="preference", statement="Help buyers first", active=True)]
    else:
        monkeypatch.setattr(brief.generation, "PROMPT_VERSION", "test-changed-prompt")
    generate(store, job, model, ctx)
    assert client.calls == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_worker_reuses_generation_but_still_commits_a_version(store: Store) -> None:
    from test_store import result, source

    from brief.worker import run_once

    p, token, _ = store.create_project("https://example.com/")
    store.finish_crawl(require_row(store.claim()), result(source()), enqueue_generation=True)
    client = CountingClient()
    model = OpenAIGenerator(client=client, model="fixture")
    await run_once(store, generator=model)
    original = require_row(store.get_project(p["id"], token))["draft"]
    store.enqueue_generation(p["id"], "same-input")
    await run_once(store, generator=model)
    state = store.get_project(p["id"], token)
    assert client.calls == 1
    assert original is not None
    assert state is not None
    assert state["proposal"]["markdown"] == original["markdown"]
    assert state["proposal"]["model_metadata"]["cache"]["status"] == "hit"
    assert original is not None
    assert state["proposal"]["id"] != original["id"]
