"""Freeze actual destination pages separately from the published llms reference."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from brief.contracts import Source
from brief.corpus import digest, write_json
from brief.crawl.extract import extract_page, source_id
from brief.crawl.fetch import FetchError, SafeFetcher

SITES = [
    "cloudflare",
    "vite",
    "fasthtml",
    "llmstxt",
    "framer",
    "picflow",
    "lowellbooks",
    "we-in-style",
    "mollieaspen",
    "salazarroofing",
    "neonelectrical",
    "tau",
    "filmconnection",
    "uamshealth",
    "healthcare-lk",
    "cake",
    "bitcoin",
    "gilesthomas",
    "answerai",
    "transitionzero",
    "trailofbits",
    "elogic",
    "greyhound",
    "terminaltrove",
    "solitek",
    "packmojo",
]


async def main() -> None:
    root = Path("evals/corpus")
    manifests = {m["id"]: m for m in json.loads((root / "manifest.json").read_text())}
    tasks = json.loads((root / "routing-tasks.json").read_text())
    semaphore = asyncio.Semaphore(4)

    async def site(id: str) -> dict[str, Any] | None:
        metadata = manifests[id]
        relevant = list(
            dict.fromkeys(t["acceptable_urls"][0] for t in tasks if t["file_id"] == id and t["acceptable_urls"])
        )[:2]
        origin = "https://" + urlsplit(metadata["final_url"]).netloc + "/"
        rows = []
        async with semaphore, SafeFetcher(timeout=18) as fetcher:
            for url in dict.fromkeys([origin] + relevant):
                sid = source_id(url)
                target = root / "evidence" / id / f"{sid}.json"
                if target.exists():
                    rows.append(json.loads(target.read_text()))
                    continue
                row: dict[str, Any] = {"url": url, "retrieved_at": datetime.now(UTC).isoformat(), "source": None}
                try:
                    response = await fetcher.get(url, allowed=lambda _: True)
                    row.update(
                        status=response.status,
                        final_url=response.url,
                        sha256=digest(response.body),
                        content_type=response.content_type,
                    )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.with_suffix(".raw").write_bytes(response.body)
                    if response.status == 200:
                        text = response.body.decode("utf-8-sig", errors="replace")
                        if "html" in response.content_type.lower() or text.lstrip().startswith("<!DOCTYPE"):
                            source, _ = extract_page(response.body, response.url)
                        else:
                            title = next((s.lstrip("# ").strip() for s in text.splitlines() if s.startswith("# ")), url)
                            source = Source(
                                id=sid,
                                url=response.url,
                                title=title[:500],
                                description="",
                                content=text[:6000],
                                markdown_url=response.url if urlsplit(response.url).path.endswith(".md") else None,
                            )
                        if source:
                            source.id = sid
                            source.content = source.content[:6000]
                            row["source"] = source.model_dump(by_alias=True)
                except FetchError as error:
                    row["error"] = str(error)
                write_json(target, row)
                rows.append(row)
        sources = [r["source"] for r in rows if r["source"]]
        gold = [r["source"]["id"] for r in rows if r["source"] and r["url"] in relevant]
        # Reviewed label correction: the programming category body is inconsistent with its label.
        if id == "lowellbooks":
            gold = [
                sid
                for sid in gold
                if sid != source_id("https://lowellbooks.com/category/computer-programming-software-engineering/")
            ]
        if len(sources) < 2 or not gold:
            print(id, "insufficient evidence", flush=True)
            return None
        print(id, len(sources), "pages", flush=True)
        return {
            "id": f"real-{id}",
            "category": metadata["category"],
            "split": metadata["split"],
            "kind": "frozen-web-pages",
            "description": "Generate from fetched source pages; published llms.txt is not a gold answer or model input.",
            "reference_file": id,
            "evidence_paths": [str(root / "evidence" / id / f"{source_id(r['url'])}.json") for r in rows],
            "input": {
                "siteUrl": origin,
                "sources": sources,
                "decisions": [],
                "dismissedTopics": [],
                "mode": "generate",
                "maxQuestions": 3,
            },
            "expected": {"include": gold, "exclude": [], "forbidden": [], "maxWords": 1000},
        }

    cases = await asyncio.gather(*(site(id) for id in SITES))
    write_json(root / "real-generation-cases.json", [c for c in cases if c])
    print(sum(c is not None for c in cases), "frozen real-site generation cases")


if __name__ == "__main__":
    asyncio.run(main())
