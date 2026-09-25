"""Download published templates as examples, never pass them off as deployed files."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from lxml import html

from brief.corpus import digest, parse_file, write_json
from brief.crawl.fetch import SafeFetcher

PAGES = [
    ("proposal", "https://llmstxt.org/domains.html"),
    ("generator", "https://llmstxtgenerator.app/llms-txt-examples"),
    ("kit", "https://llmstxtkit.com/templates/llms-txt-examples.html"),
    ("file", "https://llmsfile.com/examples/llms-txt-examples/"),
]


async def main() -> None:
    root = Path("evals/corpus/examples")
    root.mkdir(parents=True, exist_ok=True)
    records = []
    async with SafeFetcher(timeout=25) as client:
        for name, url in PAGES:
            response = await client.get(url, allowed=lambda _: True)
            (root / f"{name}.html").write_bytes(response.body)
            tree = html.fromstring(response.body)
            for i, block in enumerate(tree.xpath("//pre | //code[not(ancestor::pre)]")):
                text = "".join(block.itertext()).strip() + "\n"
                if not text.startswith("# ") or text.startswith("# ///") or "](" not in text:
                    continue
                id = f"{name}-{i}"
                (root / f"{id}.txt").write_text(text)
                parsed = parse_file(text, response.url)
                write_json(root / f"{id}.parsed.json", parsed)
                records.append(
                    {
                        "id": id,
                        "kind": "published-template",
                        "url": url,
                        "final_url": response.url,
                        "retrieved_at": datetime.now(UTC).isoformat(),
                        "selector": tree.getroottree().getpath(block),
                        "page_sha256": digest(response.body),
                        "sha256": digest(text.encode()),
                        "path": f"{id}.txt",
                        "title": parsed["headings"][0]["text"],
                        "status": response.status,
                    }
                )
    write_json(root / "manifest.json", records)
    print(f"{len(records)} published templates extracted with provenance")


if __name__ == "__main__":
    asyncio.run(main())
