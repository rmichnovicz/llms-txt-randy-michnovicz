"""Private, bounded SSE snapshots. No connection or transaction held while waiting."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder

from brief.interfaces import Disconnectable

if TYPE_CHECKING:
    from brief.live import LiveProgress
    from brief.store import Store


def read_progress(store: Store, project_id: UUID) -> dict[str, Any] | None:
    with store.db.connect() as connection:
        project = connection.execute("SELECT revision,site_id FROM projects WHERE id=%s", (project_id,)).fetchone()
        if not project:
            return None
        job = connection.execute(
            "SELECT id,status,attempt,kind,error,progress FROM jobs WHERE project_id=%s ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        siblings = connection.execute(
            """SELECT p.id,p.revision,p.auto_cancelled,
            (SELECT status FROM jobs WHERE project_id=p.id ORDER BY created_at DESC LIMIT 1) AS status
            FROM projects p WHERE site_id=%s ORDER BY p.id""",
            (project["site_id"],),
        ).fetchall()
    version = [project["revision"], str(job["id"]), job["status"], job["attempt"]] if job else [project["revision"]]
    version.append(siblings)
    return jsonable_encoder({"version": version, "job": job})


async def events(
    store: Store, project_id: UUID, request: Disconnectable, *, interval: int = 1, max_ticks: int = 60
) -> AsyncGenerator[str, None]:
    previous = None
    yield "retry: 2000\n\n"
    for tick in range(max_ticks):
        if await request.is_disconnected():
            return
        data = await asyncio.to_thread(read_progress, store, project_id)
        if data is None:
            return
        serialized = json.dumps(data, ensure_ascii=False)
        if serialized != previous:
            yield f"data: {serialized}\n\n"
            previous = serialized
        elif tick % 10 == 0:
            yield ": heartbeat\n\n"
        await asyncio.sleep(interval)
    # Bounded lifetime re-authenticates on EventSource's automatic reconnect.


async def live_events(
    store: Store,
    project_id: UUID,
    request: Disconnectable,
    live: LiveProgress,
    *,
    lifetime: float = 60,
    heartbeat: float = 10,
) -> AsyncGenerator[str, None]:
    """Read durable state on connect/invalidation, never on progress ticks."""
    previous = None
    epoch = -1
    data = None
    end = asyncio.get_running_loop().time() + lifetime
    with live.subscribe() as queue:
        yield "retry: 2000\n\n"
        while asyncio.get_running_loop().time() < end:
            if await request.is_disconnected():
                return
            if data is None or epoch != live.epoch:
                epoch = live.epoch
                data = await asyncio.to_thread(read_progress, store, project_id)
                if data is None:
                    return
            payload = dict(data)
            current = live.latest.get(str(project_id))
            if current and (
                not data["job"]
                or (str(data["job"]["id"]) == str(current["id"]) and data["job"]["status"] in {"pending", "running"})
            ):
                payload["job"] = current
                payload["version"] = [
                    data["version"][0],
                    str(current["id"]),
                    current["status"],
                    current["attempt"],
                    data["version"][-1],
                ]
            serialized = json.dumps(jsonable_encoder(payload), ensure_ascii=False)
            if serialized != previous:
                yield f"data: {serialized}\n\n"
                previous = serialized
            timeout = min(heartbeat, end - asyncio.get_running_loop().time())
            if timeout <= 0:
                return
            try:
                await asyncio.wait_for(queue.get(), timeout)
            except TimeoutError:
                yield ": heartbeat\n\n"
