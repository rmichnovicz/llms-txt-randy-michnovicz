"""Run production discovery against recorded responses; never make network calls."""

from __future__ import annotations

import asyncio
import gzip
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from brief.crawl.fetch import Response
from brief.crawl.runner import crawl

if TYPE_CHECKING:
    from brief.interfaces import URLPolicy


ROOT = Path("evals/reports/sitemap-study")


async def main() -> None:
    summaries = []
    for path in sorted(ROOT.glob("*.json")):
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or "captures" not in data:
            continue
        captures = {c["url"]: c for c in data["captures"]}

        class Replay:
            interval = 0.0

            def __init__(self, captures: dict[str, Any]) -> None:
                self.captures = captures
                self.seen: list[str] = []

            async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
                self.seen.append(url)
                record = self.captures.get(url)
                if record and record.get("file"):
                    return Response(
                        url, record["status"], "application/xml", gzip.decompress((ROOT / record["file"]).read_bytes())
                    )
                return Response(url, 404, "text/plain", b"")

        fetcher = Replay(captures)
        result = await crawl(data["site"], fetcher=fetcher, max_pages=1)
        stats = result.sitemap_discovery
        assert stats is not None
        summaries.append(
            {
                "site": data["site"],
                "discovered_including_entry": result.discovered,
                **stats,
                "recorded_fetch_seconds": round(
                    sum(captures[u]["seconds"] for u in fetcher.seen if u in captures and not u.endswith("robots.txt")),
                    3,
                ),
            }
        )
    (ROOT / (sys.argv[1] if len(sys.argv) > 1 else "production-replay.json")).write_text(
        json.dumps(summaries, indent=2) + "\n"
    )
    print(json.dumps([{k: v for k, v in s.items() if k != "trace"} for s in summaries], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
