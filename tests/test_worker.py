from __future__ import annotations

import asyncio
import threading
from typing import Any, cast

import pytest

from brief import worker
from brief.store import Store


async def test_children_have_independent_loops_and_bounded_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = threading.Lock()
    release = threading.Event()
    both_started = threading.Event()
    other_progressed = threading.Event()
    threads: set[int] = set()
    loops: set[int] = set()
    stopped: set[int] = set()
    calls = 0

    async def run_once(*args: Any, **kwargs: Any) -> bool:
        nonlocal calls
        with lock:
            calls += 1
            slot = calls
            threads.add(threading.get_ident())
            loops.add(id(asyncio.get_running_loop()))
            if calls == 2:
                both_started.set()
        try:
            if slot == 1:
                assert release.wait(5)  # Block one child's event loop deliberately.
            else:
                await asyncio.sleep(0.01)
                other_progressed.set()
            await asyncio.Event().wait()
        finally:
            stopped.add(slot)
        return True

    monkeypatch.setattr(worker, "run_once", run_once)
    monkeypatch.setenv("BRIEF_WORKER_CONCURRENCY", "2")
    supervisor = asyncio.create_task(worker.run_forever(cast(Store, None)))
    try:
        assert await asyncio.to_thread(both_started.wait, 3)
        assert await asyncio.to_thread(other_progressed.wait, 3)
        assert calls == 2
        assert len(threads) == len(loops) == 2
    finally:
        release.set()
        supervisor.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(supervisor, 3)
    assert stopped == {1, 2}


async def test_each_child_renews_its_job_and_lease_loss_is_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = threading.Lock()
    renewed: set[int] = set()
    exited: set[int] = set()
    all_renewed = threading.Event()
    lost_lease = threading.Event()
    survivor_renewed = threading.Event()
    claims = 0
    sleep = asyncio.sleep

    async def fast_heartbeat(delay: float) -> None:
        await sleep(0.01 if delay == 30 else delay)

    class FakeStore:
        def claim(self) -> dict[str, Any] | None:
            nonlocal claims
            with lock:
                claims += 1
                if claims > 2:
                    return None
                return {"id": claims, "kind": "crawl", "project_id": claims}

        def crawl_context(self, job: dict[str, Any]) -> tuple[dict[str, Any], None]:
            return {"site_url": str(job["id"])}, None

        def report_progress(self, *args: Any) -> None:
            pass

        def renew(self, job: dict[str, Any]) -> bool:
            with lock:
                renewed.add(job["id"])
                if renewed == {1, 2}:
                    all_renewed.set()
                if job["id"] == 1 and all_renewed.is_set():
                    return False
                if job["id"] == 2 and lost_lease.is_set():
                    survivor_renewed.set()
                return True

    async def crawler(url: str, previous: list[str]) -> Any:
        try:
            await asyncio.Event().wait()
        finally:
            exited.add(int(url))
            if url == "1":
                lost_lease.set()

    original = worker.run_once

    async def run_once(store: Store, **kwargs: Any) -> bool:
        return await original(store, crawler=crawler, **kwargs)

    monkeypatch.setattr(worker, "run_once", run_once)
    monkeypatch.setattr(worker.asyncio, "sleep", fast_heartbeat)
    supervisor = asyncio.create_task(worker.run_forever(cast(Store, FakeStore()), concurrency=2))
    try:
        assert await asyncio.to_thread(all_renewed.wait, 3)
        assert await asyncio.to_thread(lost_lease.wait, 3)
        assert await asyncio.to_thread(survivor_renewed.wait, 3)
        assert exited == {1}
    finally:
        supervisor.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(supervisor, 3)
    assert exited == {1, 2}


@pytest.mark.parametrize("concurrency", [0, -1])
async def test_invalid_concurrency(concurrency: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        await worker.run_forever(cast(Store, None), concurrency=concurrency)


async def test_child_reuses_slot_and_supervisor_propagates_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def run_once(*args: Any, **kwargs: Any) -> bool:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("claim failed")
        return True

    monkeypatch.setattr(worker, "run_once", run_once)
    with pytest.raises(ExceptionGroup) as error:
        await asyncio.wait_for(worker.run_forever(cast(Store, None), concurrency=1), 3)
    assert calls == 3
    assert isinstance(error.value.exceptions[0], RuntimeError)
    assert str(error.value.exceptions[0]) == "claim failed"
