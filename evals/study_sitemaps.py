"""Compare legacy discovery with scope-ranked index traversal. No model calls."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from brief.crawl.fetch import SafeFetcher, normalize_url
from brief.crawl.runner import Scope

OUT = Path("evals/reports/sitemap-study")
SITES = [
    "https://plausible.io/docs/",
    "https://tally.so/help/",
    "https://vercel.com/docs/",
    "https://www.shopify.com/blog/",
]


async def study(site: str) -> dict[str, Any]:
    scope = Scope(site)
    cache = {}
    saved_path = OUT / ((urlsplit(site).hostname or "unknown") + ".json")
    if saved_path.exists():
        for capture in json.loads(saved_path.read_text()).get("captures", []):
            if capture.get("file"):
                cache[capture["url"]] = {**capture, "body": gzip.decompress((OUT / capture["file"]).read_bytes())}
    async with SafeFetcher(timeout=8) as fetcher:

        async def read(url: str) -> dict[str, Any]:
            url = normalize_url(url)
            if url not in cache:
                start = time.monotonic()
                try:
                    r = await fetcher.get(url, allowed=scope.same_site)
                    cache[url] = {"status": r.status, "body": r.body, "seconds": time.monotonic() - start}
                except (ValueError, OSError, TimeoutError) as e:
                    cache[url] = {"status": type(e).__name__, "body": b"", "seconds": time.monotonic() - start}
            return cache[url]

        robots = await read(scope.origin + "/robots.txt")
        policy = RobotFileParser()
        if robots["status"] == 200:
            policy.parse(robots["body"].decode(errors="replace").splitlines())
        elif robots["status"] not in (404, 410):
            return {"site": site, "error": "robots unavailable", "status": robots["status"]}
        else:
            policy.parse([])
        seeds = policy.site_maps() or [scope.origin + "/sitemap.xml"]
        reports = {}
        for strategy in ["legacy", "ranked", "scoped"]:
            queue = list(seeds[:3] if strategy == "legacy" else seeds)
            seen: set[str] = set()
            urls: set[str] = set()
            size = 0
            elapsed = 0
            trace = []

            def rank(url: str, strategy: str = strategy) -> tuple[int, int, str]:
                path = urlsplit(url).path.lower()
                tokens = scope.path.strip("/").split("/")
                return (
                    0
                    if strategy == "scoped" and scope.contains(url)
                    else 1
                    if any(t in path for t in tokens if t)
                    else 2,
                    len(path.split("/")) if strategy == "scoped" else 0,
                    path,
                )

            while (
                queue
                and (strategy != "scoped" or len(urls) < 1000)
                and (len(seen) < 3 if strategy == "legacy" else elapsed < 10 and size < 4_000_000 and len(seen) < 30)
            ):
                if strategy != "legacy":
                    queue.sort(key=rank)
                u = queue.pop(0)
                try:
                    u = normalize_url(u)
                except ValueError:
                    continue
                if u in seen or not scope.same_site(u):
                    continue
                seen.add(u)
                r = await read(u)
                size += len(r["body"])
                elapsed += r["seconds"]
                record: dict[str, Any] = {
                    "url": u,
                    "status": r["status"],
                    "bytes": len(r["body"]),
                    "seconds": round(r["seconds"], 3),
                }
                trace.append(record)
                if r["status"] != 200:
                    continue
                try:
                    root = fromstring(r["body"])
                    locs = [el.text.strip() for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "loc" and el.text]
                    if root.tag.rsplit("}", 1)[-1] == "sitemapindex":
                        queue.extend(locs[:3] if strategy == "legacy" else locs)
                    else:
                        for loc in locs if strategy == "scoped" else locs[:1000]:
                            try:
                                loc = normalize_url(loc)
                                if (
                                    scope.contains(loc)
                                    and policy.can_fetch("BriefBot/0.1", loc)
                                    and (strategy != "scoped" or len(urls) < 1000)
                                ):
                                    urls.add(loc)
                            except ValueError:
                                pass
                    record["locations"] = len(locs)
                except (ParseError, DefusedXmlException, ValueError) as e:
                    record["parse_error"] = type(e).__name__
            reports[strategy] = {
                "eligible_urls": len(urls),
                "urls": sorted(urls),
                "fetches": len(seen),
                "bytes": size,
                "recorded_fetch_seconds": round(elapsed, 3),
                "remaining_sitemaps": len(queue),
                "trace": trace,
            }
        for url, r in cache.items():
            if r["status"] == 200:
                name = hashlib.sha256(url.encode()).hexdigest()[:16] + ".xml.gz"
                (OUT / name).write_bytes(gzip.compress(r["body"]))
                r["file"] = name
        report: dict[str, Any] = {
            "site": site,
            "robots_status": robots["status"],
            "strategies": reports,
            "captures": [{k: v for k, v in {"url": u, **r}.items() if k != "body"} for u, r in cache.items()],
        }
        (OUT / ((urlsplit(site).hostname or "unknown") + ".json")).write_text(json.dumps(report, indent=2) + "\n")
        return {
            "site": site,
            **{k: {a: b for a, b in v.items() if a not in {"urls", "trace"}} for k, v in reports.items()},
        }


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results = await asyncio.gather(*(study(site) for site in SITES))
    (OUT / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
