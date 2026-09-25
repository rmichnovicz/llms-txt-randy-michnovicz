"""Real cached HTML through extraction, durable refresh, generation and review.

The generator is deliberately deterministic: these are workflow assertions, not
claims about model quality. No network or model credentials are needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from refresh_replay import CASES, Replay, body_for
from test_generation_jobs import Generator

from brief import editor
from brief.crawl.fetch import FetchError, Response
from brief.db import require_row
from brief.worker import run_once

if TYPE_CHECKING:
    from brief.contracts import GenerationInput
    from brief.model import Completion
    from brief.store import Store


class RecordingGenerator(Generator):
    def __init__(self) -> None:
        self.inputs: list[GenerationInput] = []

    def generate(self, context: GenerationInput) -> Completion:
        self.inputs.append(context)
        completion = super().generate(context)
        # Force the rendered artifact to depend on new evidence, not a fixed fixture.
        completion.raw["guide"]["summary"]["text"] = " ".join(context.sources[0].content.split())[:1000]
        completion.raw["guide"]["sections"][0]["links"] = [
            {"sourceId": s.id, "label": s.title, "description": None} for s in context.sources
        ]
        return completion


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
async def test_archived_html_changes_extracted_evidence(case: dict[str, Any]) -> None:
    before = await Replay(case).crawl(case["url"])
    after = await Replay(case, 1).crawl(case["url"], [case["url"]])
    assert before.sources and after.sources
    assert before.observations[0].hash != after.observations[0].hash
    if case["id"] == "h5bp":
        assert "Normalize.css" in before.sources[0].content
        assert "Normalize.css" not in after.sources[0].content
    if case["id"] == "jquery":
        assert "maintenance-only" not in before.sources[0].content
        assert "maintenance-only" in after.sources[0].content


async def test_archive_miss_is_not_a_removal_and_cache_integrity_is_checked() -> None:
    replay = Replay(CASES[0])
    with pytest.raises(FetchError, match="not evidence of removal"):
        await replay.get("https://jquery.com/not-captured/", allowed=lambda _: True)
    with pytest.raises(ValueError, match="checksum"):
        body_for({**CASES[0]["versions"][0], "sha256": "incorrect"})


@pytest.mark.integration
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
async def test_refresh_keeps_manual_draft_then_accepts_archived_change(store: Store, case: dict[str, Any]) -> None:
    project, token, _ = store.create_project(case["url"])
    pid = project["id"]
    state = lambda: require_row(store.get_project(pid, token))
    generator = RecordingGenerator()
    await run_once(store, crawler=Replay(case).crawl, generator=generator)
    await run_once(store, generator=generator)
    first = state()
    initial_snapshot = first["snapshot"]
    decision = editor.save_decision(
        store, pid, first["revision"], statement="Prioritize getting started", kind="preference"
    )
    await run_once(store, generator=generator)
    manual = "# Owner draft\n\nKeep my wording until I review the website changes.\n"
    editor.save_document(store, pid, state()["revision"], manual)
    manual_id = state()["draft_version_id"]

    # Exact same HTML: immutable check snapshot, no generation or proposal.
    calls = len(generator.inputs)
    store.enqueue_refresh(pid, "identical")
    await run_once(store, crawler=Replay(case).crawl, generator=generator)
    assert not await run_once(store, generator=generator)
    assert len(generator.inputs) == calls
    assert state()["snapshot"]["changes"]["changed"] is False

    # Real new archive: model sees new sources plus saved owner direction.
    store.enqueue_refresh(pid, "new-archive")
    await run_once(store, crawler=Replay(case, 1).crawl, generator=generator)
    await run_once(store, generator=generator)
    changed = state()
    assert changed["snapshot"]["changes"]["modified"] == [case["url"]]
    assert changed["draft_version_id"] == manual_id
    assert changed["draft"]["markdown"] == manual
    proposal = changed["proposal"]
    assert proposal is not None
    assert proposal["snapshot_id"] == changed["latest_snapshot_id"]
    assert proposal is not None
    assert proposal["generation_input"]["sources"] != first["draft"]["generation_input"]["sources"]
    assert generator.inputs[-1].decisions[0].id == decision["decision_id"]
    assert len(generator.inputs) == calls + 1
    with store.db.connect() as connection:
        saved = connection.execute(
            "SELECT sources FROM crawl_snapshots WHERE id=%s", (initial_snapshot["id"],)
        ).fetchone()
        assert initial_snapshot is not None
        assert saved is not None
        assert saved["sources"] == initial_snapshot["sources"]
    assert proposal is not None
    editor.use_version(store, pid, changed["revision"], proposal["id"])
    accepted = state()
    assert proposal is not None
    assert accepted["draft_version_id"] == proposal["id"]
    assert accepted["proposal"] is None
    assert accepted["decisions"][0]["active"]
    assert any(v["id"] == manual_id for v in accepted["versions"])


@pytest.mark.integration
@pytest.mark.parametrize("failure", [404, 410, 503, "robots", "uncaptured"])
async def test_partial_refresh_retains_unavailable_page_and_only_confirms_real_removal(
    store: Store, failure: int | str
) -> None:
    case = CASES[0]
    url = case["auxiliary_pages"][0]["url"]
    project, token, _ = store.create_project(case["url"])
    pid = project["id"]
    generator = RecordingGenerator()
    await run_once(store, crawler=Replay(case, extra=True).crawl, generator=generator)
    await run_once(store, generator=generator)
    first = store.get_project(pid, token)
    assert first is not None
    assert len(first["snapshot"]["sources"]) == 2
    for attempt in range(2):
        overrides = {}
        if isinstance(failure, int):
            overrides[url] = Response(url, failure, "text/plain", b"Unavailable")
        if failure == "robots":
            robots = "https://jquery.com/robots.txt"
            overrides[robots] = Response(robots, 200, "text/plain", b"User-agent: *\nDisallow: /browser-support/\n")
        replay = Replay(case, extra=failure != "uncaptured", overrides=overrides)
        store.enqueue_refresh(pid, f"failure-{attempt}")
        await run_once(store, crawler=replay.crawl, generator=generator)
        current = store.get_project(pid, token)
        removed = attempt == 1 and failure in (404, 410)
        assert current is not None
        assert (url in current["snapshot"]["changes"]["removed"]) == removed
        assert (url in [s["url"] for s in current["snapshot"]["sources"]]) != removed
        assert current["draft_version_id"] == first["draft_version_id"]
        if removed:
            assert await run_once(store, generator=generator)
            assert url not in [s.url for s in generator.inputs[-1].sources]
            assert url not in require_row(store.get_project(pid, token))["proposal"]["markdown"]
        else:
            assert url in current["snapshot"]["changes"]["unavailable"]
            assert not await run_once(store, generator=generator)
    # Recovery resets missing-page history and restores deleted evidence.
    store.enqueue_refresh(pid, "recovered")
    await run_once(store, crawler=Replay(case, extra=True).crawl, generator=generator)
    recovered = store.get_project(pid, token)
    assert recovered is not None
    assert len(recovered["snapshot"]["sources"]) == 2
    assert (url in recovered["snapshot"]["changes"]["added"]) == (failure in (404, 410))


@pytest.mark.integration
async def test_total_outage_preserves_last_usable_snapshot_and_document(store: Store) -> None:
    case = CASES[1]
    project, token, _ = store.create_project(case["url"])
    pid = project["id"]
    generator = RecordingGenerator()
    await run_once(store, crawler=Replay(case).crawl, generator=generator)
    await run_once(store, generator=generator)
    first = store.get_project(pid, token)
    store.enqueue_refresh(pid, "outage")
    failed = Replay(case, overrides={case["url"]: Response(case["url"], 503, "text/plain", b"Down")})
    await run_once(store, crawler=failed.crawl, generator=generator)
    current = store.get_project(pid, token)
    assert current is not None
    assert first is not None
    assert current["latest_snapshot_id"] == first["latest_snapshot_id"]
    assert current["draft_version_id"] == first["draft_version_id"]
    assert len(generator.inputs) == 1
    with store.db.connect() as connection:
        rows = connection.execute("SELECT status FROM crawl_snapshots WHERE project_id=%s", (pid,)).fetchall()
        assert len(rows) == 2 and any(r["status"] == "failed" for r in rows)


@pytest.mark.integration
async def test_cosmetic_html_change_does_not_generate_new_draft(store: Store) -> None:
    case = CASES[1]
    project, token, _ = store.create_project(case["url"])
    generator = RecordingGenerator()
    await run_once(store, crawler=Replay(case).crawl, generator=generator)
    await run_once(store, generator=generator)
    body = body_for(case["versions"][0]).replace(b"</head>", b"<!-- synthetic analytics deployment -->\n</head>")
    assert body != body_for(case["versions"][0])
    store.enqueue_refresh(project["id"], "cosmetic")
    replay = Replay(case, overrides={case["url"]: Response(case["url"], 200, "text/html", body)})
    await run_once(store, crawler=replay.crawl, generator=generator)
    assert not await run_once(store, generator=generator)
    assert len(generator.inputs) == 1
    assert require_row(store.get_project(project["id"], token))["snapshot"]["changes"]["changed"] is False


@pytest.mark.integration
async def test_success_between_missing_checks_resets_removal_counter(store: Store) -> None:
    case = CASES[0]
    url = case["auxiliary_pages"][0]["url"]
    project, token, _ = store.create_project(case["url"])
    pid = project["id"]
    generator = RecordingGenerator()
    await run_once(store, crawler=Replay(case, extra=True).crawl, generator=generator)
    await run_once(store, generator=generator)
    for attempt, status in enumerate([404, 200, 404]):
        overrides = {} if status == 200 else {url: Response(url, status, "text/plain", b"Missing")}
        store.enqueue_refresh(pid, f"flapping-{attempt}")
        await run_once(store, crawler=Replay(case, extra=True, overrides=overrides).crawl, generator=generator)
        current = store.get_project(pid, token)
        assert current is not None
        assert current["snapshot"]["changes"]["removed"] == []
        assert len(current["snapshot"]["sources"]) == 2
        assert not await run_once(store, generator=generator)
    assert len(generator.inputs) == 1


@pytest.mark.integration
async def test_generation_failure_after_refresh_preserves_draft_and_new_evidence(store: Store) -> None:
    from brief.model import ModelError

    class Broken:
        def generate(self, context: GenerationInput) -> Completion:
            raise ModelError("Fixture provider unavailable", retryable=False)

    case = CASES[1]
    project, token, _ = store.create_project(case["url"])
    pid = project["id"]
    generator = RecordingGenerator()
    await run_once(store, crawler=Replay(case).crawl, generator=generator)
    await run_once(store, generator=generator)
    first = store.get_project(pid, token)
    store.enqueue_refresh(pid, "changed-before-model-failure")
    await run_once(store, crawler=Replay(case, 1).crawl, generator=generator)
    await run_once(store, generator=Broken())
    current = store.get_project(pid, token)
    assert current is not None
    assert first is not None
    assert current["latest_snapshot_id"] != first["latest_snapshot_id"]
    assert current["draft_version_id"] == first["draft_version_id"]
    assert current["proposal"] is None
    assert current["jobs"][0]["status"] == "failed"
    assert "Normalize.css" not in current["snapshot"]["sources"][0]["content"]
