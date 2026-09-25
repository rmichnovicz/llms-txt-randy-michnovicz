from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from test_store import result, source

from brief.api import create_app
from brief.db import require_row
from brief.progress import events, read_progress
from brief.store import LeaseLost
from brief.worker import run_once

if TYPE_CHECKING:
    from brief.crawl.runner import CrawlResult
    from brief.store import Store


pytestmark = pytest.mark.integration


class Connected:
    async def is_disconnected(self) -> bool:
        return False


async def test_stream_reports_progress_and_completion_without_private_inputs(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")
    job = require_row(store.claim())
    store.report_progress(job, {"message": "Read: Pricing", "pages_read": 2})
    chunks = [chunk async for chunk in events(store, project["id"], Connected(), interval=0, max_ticks=1)]
    payload = json.loads(chunks[1].removeprefix("data: "))
    assert payload["job"]["progress"]["pages_read"] == 2
    assert token not in "".join(chunks)
    assert "management_token_hash" not in "".join(chunks)
    version = payload["version"]
    store.finish_crawl(job, result(source()))
    assert require_row(read_progress(store, project["id"]))["version"] != version
    with pytest.raises(LeaseLost):
        store.report_progress(job, {"message": "stale update"})


def test_sse_requires_project_access(store: Store) -> None:
    project, _, _ = store.create_project("https://example.com/")
    _other, token, _ = store.create_project("https://other.example.com/")
    with TestClient(create_app(store)) as client:
        path = f"/api/projects/{project['id']}/events"
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": f"Bearer {token}"}).status_code == 404


async def test_worker_persists_truthful_stage_progress(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")

    async def crawler(*args: Any) -> CrawlResult:
        return result(source())

    await run_once(store, crawler=crawler)
    state = store.get_project(project["id"], token)
    assert state is not None
    progress = state["jobs"][0]["progress"]
    assert progress["pages_read"] == 1
    assert progress["started_at"]
    assert len(progress["recent"]) == 2


async def test_real_extraction_emits_page_counts_and_titles() -> None:
    from refresh_replay import CASES, Replay

    from brief.crawl.runner import crawl

    updates = []

    async def progress(data: dict[str, Any]) -> None:
        updates.append(data)

    case = CASES[1]
    output = await crawl(case["url"], fetcher=Replay(case), max_pages=1, progress=progress)
    assert updates[0]["message"].startswith("Checking")
    assert updates[-1]["pages_read"] == len(output.sources) == 1
    assert output.sources[0].title[:150] in updates[-1]["message"]


def test_retry_replaces_stale_working_message(store: Store) -> None:
    project, _, _ = store.create_project("https://example.com/")
    job = require_row(store.claim())
    store.report_progress(job, {"message": "Reading a page", "started_at": "old-attempt"})
    store.fail(job, "Temporary failure", retryable=True)
    progress = require_row(read_progress(store, project["id"]))["job"]["progress"]
    assert progress["stage"] == "waiting"
    assert "retry" in progress["message"]
    assert "started_at" not in progress


async def test_live_stream_uses_memory_for_progress_and_heartbeats(store: Store, monkeypatch: MonkeyPatch) -> None:
    import asyncio

    from brief import progress
    from brief.live import LiveProgress

    project, _, _ = store.create_project("https://example.com/")
    job = require_row(store.claim())
    live = LiveProgress()
    reads = []
    original = progress.read_progress

    def counted(*args: Any) -> dict[str, Any] | None:
        reads.append(1)
        return original(*args)

    monkeypatch.setattr(progress, "read_progress", counted)
    stream = progress.live_events(store, project["id"], Connected(), live, heartbeat=0.02)
    await anext(stream)  # Retry hint.
    await anext(stream)  # Initial durable snapshot.
    assert len(reads) == 1
    live.progress(job, {"message": "Page 1"})
    await asyncio.sleep(0)
    assert "Page 1" in await anext(stream)
    assert "heartbeat" in await anext(stream)
    assert len(reads) == 1
    store.finish_crawl(job, result(source()))
    live.invalidate(project["id"])
    await asyncio.sleep(0)
    assert "succeeded" in await anext(stream)
    assert len(reads) == 2
    await stream.aclose()
    assert not live.subscribers
    assert not live.latest


async def test_live_subscribers_are_bounded_and_project_private(store: Store) -> None:
    import asyncio

    from brief.live import LiveProgress
    from brief.progress import live_events

    project, _, _ = store.create_project("https://example.com/")
    other, _, _ = store.create_project("https://other.example.com/")
    job: dict[str, Any] = {
        "id": "other-job",
        "project_id": other["id"],
        "status": "running",
        "kind": "refresh",
        "attempt": 1,
    }
    live = LiveProgress()
    with live.subscribe() as slow:
        for i in range(100):
            live.progress(job, {"message": f"PRIVATE-{i}"})
        await asyncio.sleep(0)
        assert slow.qsize() == 1
        assert live.latest[str(other["id"])]["progress"]["message"] == "PRIVATE-99"
    stream = live_events(store, project["id"], Connected(), live, heartbeat=0.01)
    await anext(stream)
    assert "PRIVATE" not in await anext(stream)
    assert "heartbeat" in await anext(stream)
    await stream.aclose()


async def test_embedded_worker_checkpoints_stages_not_each_page(store: Store, monkeypatch: MonkeyPatch) -> None:
    from brief import worker
    from brief.live import LiveProgress

    project, _, _ = store.create_project("https://example.com/")
    live = LiveProgress()
    writes = []
    original = store.report_progress

    def checkpoint(*args: Any) -> None:
        writes.append(args[1])
        return original(*args)

    async def crawler(url: str, previous: list[str], **options: Any) -> CrawlResult:
        for i in range(100):
            await options["progress"]({"stage": "reading", "message": f"Page {i}"})
        return result(source())

    monkeypatch.setattr(worker, "crawl", crawler)
    monkeypatch.setattr(store, "report_progress", checkpoint)
    # Skip the separate external publication probe in this deterministic test.
    with store.db.connect() as c:
        c.execute("UPDATE projects SET existing_guide_check='{}' WHERE id=%s", (project["id"],))
    await worker.run_once(store, crawler=crawler, live=live)
    assert len(writes) == 3  # discovering, reading, saving
    assert writes[-1]["pages_read"] == 1


async def test_demo_worker_thread_does_not_block_api_loop(monkeypatch: MonkeyPatch) -> None:
    import asyncio
    import threading

    from brief import worker
    from brief.live import DemoWorker, LiveProgress

    entered = threading.Event()
    release = threading.Event()

    async def blocking_worker(*args: Any, **kwargs: Any) -> None:
        entered.set()
        release.wait(2)  # Deliberately blocks the worker's loop, never the API loop.
        await asyncio.sleep(100)

    monkeypatch.setattr(worker, "run_forever", blocking_worker)
    demo = DemoWorker(cast("Store", None), None, LiveProgress())
    await demo.start()
    try:
        assert entered.is_set()
        await asyncio.wait_for(asyncio.sleep(0.01), timeout=0.2)
    finally:
        release.set()
        await demo.stop()
    assert not demo.thread.is_alive()


async def test_live_progress_can_arrive_from_worker_thread() -> None:
    import asyncio

    from brief.live import LiveProgress

    live = LiveProgress()
    job = {"project_id": "project", "id": "job", "status": "running"}
    with live.subscribe() as queue:
        await asyncio.to_thread(live.progress, job, {"message": "Thread-safe delivery"})
        await asyncio.wait_for(queue.get(), 0.5)
        assert live.latest["project"]["progress"]["message"] == "Thread-safe delivery"


def test_embedded_lifespan_starts_and_stops_worker(store: Store, monkeypatch: MonkeyPatch) -> None:
    import asyncio
    import threading

    from brief import worker

    started, stopped = threading.Event(), threading.Event()

    async def idle(*args: Any, **kwargs: Any) -> None:
        started.set()
        try:
            await asyncio.sleep(100)
        finally:
            stopped.set()

    monkeypatch.setattr(worker, "run_forever", idle)
    monkeypatch.setenv("BRIEF_EMBEDDED_WORKER", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = create_app(store)
    with TestClient(app) as client:
        assert started.is_set()
        assert client.get("/health").status_code == 200
        assert app.state.live is not None
    assert stopped.is_set()
