"""Compact persisted frontier and section-balanced model candidates."""

from __future__ import annotations

import json
import zlib
from collections import defaultdict, deque
from collections.abc import Collection, Iterable
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit
from uuid import UUID

from psycopg import Connection

from brief.crawl.planning import priority

if TYPE_CHECKING:
    from brief.db import Database


def section(url: str, root: str) -> str:
    path = urlsplit(url).path
    base = urlsplit(root).path.rstrip("/")
    relative = path[len(base) :] if base and (path == base or path.startswith(base + "/")) else path
    return relative.strip("/").split("/")[0] or "(entry)"


def balanced(
    urls: Iterable[str], root: str, previous: Collection[str] = (), *, character_budget: int = 24000
) -> list[str]:
    groups = defaultdict(list)
    for url in urls:
        groups[section(url, root)].append(url)
    queues = [deque(sorted(group, key=lambda u: priority(u, root, previous))) for group in groups.values()]
    queues.sort(key=lambda q: priority(q[0], root, previous))
    result, size = [], 2
    while queues:
        remaining = []
        for q in queues:
            url = q.popleft()
            cost = len(json.dumps(url, ensure_ascii=False).encode()) + 1
            if size + cost <= character_budget:
                result.append(url)
                size += cost
            if q:
                remaining.append(q)
        queues = remaining
        if size >= character_budget - 2051:
            break
    return result


def load(db: Database, project_id: UUID) -> dict[str, Any] | None:
    with db.connect() as c:
        row = c.execute("SELECT payload FROM discovery_frontiers WHERE project_id=%s", (project_id,)).fetchone()
    return json.loads(zlib.decompress(bytes(row["payload"]))) if row else None


def save(c: Connection[dict[str, Any]], project_id: UUID, state: dict[str, Any]) -> None:
    c.execute(
        """INSERT INTO discovery_frontiers(project_id,payload) VALUES (%s,%s)
        ON CONFLICT(project_id) DO UPDATE SET payload=excluded.payload,updated_at=now()""",
        (project_id, zlib.compress(json.dumps(state, separators=(",", ":"), ensure_ascii=False).encode())),
    )
