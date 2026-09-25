"""Demo-local progress fan-out. Worker threads never wait for viewers."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from brief.interfaces import Generator
    from brief.store import Store


class LiveProgress:
    def __init__(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.latest: dict[str, dict[str, Any]] = {}
        self.epoch = 0
        self.subscribers: set[asyncio.Queue[None]] = set()

    def _wake(self) -> None:
        for queue in self.subscribers:
            if queue.empty():
                queue.put_nowait(None)

    def progress(self, job: dict[str, Any], progress: dict[str, Any]) -> None:
        # Copy before crossing threads: callers may mutate their recent-event list.
        data = {key: job.get(key) for key in ("id", "status", "attempt", "kind", "error")}
        data["progress"] = progress

        def deliver() -> None:
            self.latest[str(job["project_id"])] = data
            self._wake()

        self.loop.call_soon_threadsafe(deliver)

    def invalidate(self, project_id: object = None) -> None:
        def deliver() -> None:
            if project_id is not None:
                self.latest.pop(str(project_id), None)
            self.epoch += 1
            self._wake()

        self.loop.call_soon_threadsafe(deliver)

    @contextmanager
    def subscribe(self) -> Iterator[asyncio.Queue[None]]:
        queue: asyncio.Queue[None] = asyncio.Queue(maxsize=1)
        self.subscribers.add(queue)
        try:
            yield queue
        finally:
            self.subscribers.discard(queue)


class DemoWorker:
    """One isolated worker event loop; normal thread-offloaded model/extraction calls."""

    def __init__(self, store: Store, generator: Generator | None, live: LiveProgress) -> None:
        self.store, self.generator, self.live = store, generator, live
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, name="brief-worker", daemon=True)

    def _run(self) -> None:
        from brief.worker import run_forever

        async def main() -> None:
            self.loop = asyncio.get_running_loop()
            self.task = asyncio.current_task()
            assert self.task is not None
            self.ready.set()
            try:
                await run_forever(self.store, generator=self.generator, live=self.live)
            except asyncio.CancelledError:
                pass

        asyncio.run(main())

    async def start(self) -> None:
        self.thread.start()
        await asyncio.to_thread(self.ready.wait)

    async def stop(self) -> None:
        if self.task is not None:
            self.loop.call_soon_threadsafe(self.task.cancel)
        # In-flight blocking calls may finish; database lease/revision guards remain authoritative.
        await asyncio.to_thread(self.thread.join, 5)
