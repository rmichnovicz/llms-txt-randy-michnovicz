"""Site-private extracted-page cache; HTTP validators are always rechecked."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from psycopg.types.json import Jsonb

from brief.crawl.extract import EXTRACTION_VERSION

if TYPE_CHECKING:
    from brief.contracts import Source
    from brief.db import Database


class PageCache:
    def __init__(self, db: Database, site_id: UUID) -> None:
        self.db, self.site_id = db, site_id

    def get(self, url: str) -> dict[str, Any] | None:
        with self.db.connect() as c:
            return c.execute(
                "SELECT * FROM page_cache WHERE site_id=%s AND url=%s AND extraction_version=%s",
                (self.site_id, url, EXTRACTION_VERSION),
            ).fetchone()

    def delete(self, url: str) -> None:
        with self.db.connect() as c:
            c.execute("DELETE FROM page_cache WHERE site_id=%s AND url=%s", (self.site_id, url))

    def put(self, url: str, source: Source, links: list[str], headers: dict[str, str]) -> str:
        directives = headers.get("cache-control", "").lower()
        vary = {v.strip().lower() for v in headers.get("vary", "").split(",") if v.strip()}
        if "no-store" in directives or "private" in directives or vary - {"accept-encoding", "accept"}:
            self.delete(url)
            return (
                "not stored: Cache-Control private/no-store"
                if "no-store" in directives or "private" in directives
                else "not stored: unsupported Vary"
            )
        with self.db.connect() as c:
            c.execute(
                """INSERT INTO page_cache(site_id,url,etag,last_modified,source,links,extraction_version)
                VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(site_id,url) DO UPDATE SET
                etag=excluded.etag,last_modified=excluded.last_modified,source=excluded.source,
                links=excluded.links,extraction_version=excluded.extraction_version,checked_at=now()""",
                (
                    self.site_id,
                    url,
                    headers.get("etag"),
                    headers.get("last-modified"),
                    Jsonb(source.model_dump()),
                    Jsonb(links),
                    EXTRACTION_VERSION,
                ),
            )
        return (
            "stored with validator"
            if headers.get("etag") or headers.get("last-modified")
            else "stored without validator"
        )
