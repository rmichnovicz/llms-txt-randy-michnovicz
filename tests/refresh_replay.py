"""Offline website archive replay. Unknown URLs are unavailable, never invented 404s."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from brief.crawl.fetch import FetchError, Response
from brief.crawl.runner import CrawlResult, crawl

if TYPE_CHECKING:
    from brief.interfaces import URLPolicy


ROOT = Path(__file__).parent / "fixtures" / "refresh"
CASES = json.loads((ROOT / "manifest.json").read_text())["cases"]


def body_for(record: dict[str, Any]) -> bytes:
    body = (ROOT / record["file"]).read_bytes()
    if hashlib.sha256(body).hexdigest() != record["sha256"]:
        raise ValueError(f"Archive checksum mismatch: {record['file']}")
    return body


class Replay:
    interval = 0.0

    def __init__(
        self,
        case: dict[str, Any],
        version: int = 0,
        *,
        overrides: dict[str, Response] | None = None,
        extra: bool = False,
    ) -> None:
        self.case = case
        record = case["versions"][version]
        self.pages = {case["url"]: Response(case["url"], 200, "text/html", body_for(record))}
        if extra:
            for page in case.get("auxiliary_pages", []):
                self.pages[page["url"]] = Response(page["url"], 200, "text/html", body_for(page))
        # Robots/sitemap responses are explicitly synthetic, not historical captures.
        parts = urlsplit(case["url"])
        origin = f"{parts.scheme}://{parts.netloc}"
        self.pages[origin + "/robots.txt"] = Response(
            origin + "/robots.txt", 200, "text/plain", b"User-agent: *\nAllow: /\n"
        )
        self.pages[origin + "/sitemap.xml"] = Response(origin + "/sitemap.xml", 404, "text/plain", b"")
        self.pages.update(overrides or {})
        self.requests: list[str] = []

    async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
        self.requests.append(url)
        verdict = allowed(url)
        if not (await verdict if inspect.isawaitable(verdict) else verdict):
            raise FetchError("Outside replay crawl scope")
        if url not in self.pages:
            raise FetchError("URL not captured in archive (not evidence of removal)")
        return self.pages[url]

    async def crawl(self, url: str, previous: Sequence[str] = ()) -> CrawlResult:
        # Small bounded captures intentionally produce partial coverage.
        return await crawl(url, previous, fetcher=self, max_pages=8)
