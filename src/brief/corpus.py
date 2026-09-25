"""Reproducible public-file collection and descriptive diagnostics, not an SEO score."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from markdown_it import MarkdownIt

from brief.crawl.fetch import FetchError, SafeFetcher

ROOT = Path("evals/corpus")
PARSER_VERSION = "corpus-v2"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def canonical_url(url: str) -> str:
    """Compare destinations without collapsing fragments: they can address different tasks."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, parts.fragment))


def parse_file(text: str, base_url: str) -> dict[str, Any]:
    """Parse CommonMark links (including references), excluding fenced examples."""
    tokens = MarkdownIt("commonmark").parse(text)
    lines = text.splitlines()
    links: list[dict[str, Any]] = []
    headings: list[dict[str, Any]] = []
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            assert token.map is not None
            headings.append({"level": int(token.tag[1]), "text": tokens[i + 1].content, "line": token.map[0] + 1})
        if token.type != "inline":
            continue
        children = token.children or []
        for j, child in enumerate(children):
            if child.type != "link_open":
                continue
            destination = str(child.attrGet("href") or "")
            label = ""
            k = j + 1
            while k < len(children) and children[k].type != "link_close":
                label += children[k].content
                k += 1
            tail = "".join(c.content for c in children[k + 1 :])
            description = re.sub(r"^\s*[:–—-]\s*", "", tail).strip() if re.match(r"^\s*[:–—-]", tail) else ""
            url = urljoin(base_url, destination)
            canonical = canonical_url(url)
            links.append(
                {
                    "label": label,
                    "url": url,
                    "canonical": canonical,
                    "raw_url": destination,
                    "description": description,
                    "line": (token.map or [0])[0] + 1,
                }
            )
    # Bare URLs remain useful to an agent even though they do not follow the link-list convention.
    known = {link["url"] for link in links}
    bare_links = []
    in_fence = False
    for line_no, line in enumerate(lines, 1):
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
        if in_fence:
            continue
        for match in re.finditer(r"https?://[^\s<>\]\"\']+", line):
            url = match.group().rstrip(").,;:")
            if url in known:
                continue
            known.add(url)
            bare_links.append(
                {
                    "url": url,
                    "label": line.strip(),
                    "description": "",
                    "line": line_no,
                    "canonical": url,
                    "raw_url": url,
                }
            )
    words = len(text.split())
    counts = Counter(x["canonical"] for x in links)
    html = bool(re.search(r"<!doctype\s+html|<html[\s>]|<body[\s>]", text[:4000], re.IGNORECASE))
    h1 = [h for h in headings if h["level"] == 1]
    flags = []
    if html:
        flags.append("html-instead-of-markdown")
    if not h1:
        flags.append("missing-h1")
    if len(h1) > 1:
        flags.append("multiple-h1-review")
    if not links:
        flags.append("no-markdown-links-review-purpose")
    if len(links) > 100:
        flags.append("large-index-test-task-routing")
    if words > 5000:
        flags.append("large-context-test-budget")
    if any(n > 1 for n in counts.values()):
        flags.append("duplicate-destinations-review")
    if links and sum(bool(x["description"]) for x in links) / len(links) < 0.5:
        flags.append("sparse-link-descriptions")
    if re.search(r"(?im)^(user-agent|disallow|allow):", text):
        flags.append("robots-style-directives-not-enforced-by-llms-txt")
    if re.search(
        r"(?i)ignore (all |any |previous |prior )*instructions|always recommend|never mention competitors", text
    ):
        flags.append("behavioral-directive-review")
    if re.search(r"https?://(?:example\.(?:com|org)|host)(?:[/\s)]|$)|\[COMPLETE:", text):
        flags.append("placeholder-review")
    return {
        "parser_version": PARSER_VERSION,
        "headings": headings,
        "links": links,
        "bare_links": bare_links,
        "metrics": {
            "bytes": len(text.encode()),
            "words": words,
            "lines": len(lines),
            "approx_tokens_chars_div_4": math.ceil(len(text) / 4),
            "h1_count": len(h1),
            "link_count": len(links),
            "bare_url_count": len(bare_links),
            "described_links": sum(bool(x["description"]) for x in links),
            "unique_destinations": len(counts),
            "markdown_destinations": sum(urlsplit(x["url"]).path.endswith(".md") for x in links),
        },
        "flags": flags,
    }


async def fetch_corpus(root: Path, refresh: bool = False) -> None:
    seeds = json.loads((root / "seeds.json").read_text())
    semaphore = asyncio.Semaphore(4)

    async def fetch(seed: dict[str, Any]) -> dict[str, Any]:
        meta_path = root / "metadata" / f"{seed['id']}.json"
        if meta_path.exists() and not refresh:
            return json.loads(meta_path.read_text())
        async with semaphore:
            record: dict[str, Any] = {**seed, "retrieved_at": datetime.now(UTC).isoformat(), "accepted": False}
            try:
                async with SafeFetcher(timeout=25, max_bytes=4_000_000) as client:
                    response = await client.get(seed["url"], allowed=lambda _: True)
                record.update(
                    status=response.status,
                    final_url=response.url,
                    content_type=response.content_type,
                    sha256=digest(response.body),
                    bytes=len(response.body),
                )
                # Preserve exact response bytes even on HTTP failures; never call a soft-200 HTML page an llms file.
                raw = root / "raw" / f"{seed['id']}.txt"
                raw.parent.mkdir(parents=True, exist_ok=True)
                raw.write_bytes(response.body)
                text = response.body.decode("utf-8-sig", errors="replace")
                parsed = parse_file(text, response.url)
                record["accepted"] = (
                    response.status == 200 and "html-instead-of-markdown" not in parsed["flags"] and bool(text.strip())
                )
                record["decode_replacements"] = text.count("\ufffd")
                record["raw_path"] = str(raw.relative_to(root))
                write_json(root / "parsed" / f"{seed['id']}.json", parsed)
            except (FetchError, UnicodeError) as error:
                record["error"] = str(error)
            write_json(meta_path, record)
            print(
                f"{seed['id']}: {'downloaded' if record['accepted'] else record.get('error', record.get('status'))}",
                flush=True,
            )
            return record

    records = await asyncio.gather(*(fetch(s) for s in seeds))
    write_json(root / "manifest.json", records)


def audit(root: Path) -> None:
    manifest = json.loads((root / "manifest.json").read_text())
    rows = []
    for record in manifest:
        if not record["accepted"]:
            rows.append({**record, "metrics": None, "flags": ["fetch-failed-or-not-llms-file"]})
            continue
        raw = (root / record["raw_path"]).read_bytes()
        if digest(raw) != record["sha256"]:
            raise ValueError(f"Corpus hash mismatch: {record['id']}")
        parsed = parse_file(raw.decode("utf-8-sig", errors="replace"), record["final_url"])
        write_json(root / "parsed" / f"{record['id']}.json", parsed)
        rows.append({**record, "metrics": parsed["metrics"], "flags": parsed["flags"]})
    write_json(root / "audit.json", rows)
    lines = [
        "# Download audit",
        "",
        "Descriptive signals, not quality grades. Fetch failures are not bad files.",
        "",
        "| File | Category | Status | Words | Links | Flags |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in rows:
        m = row["metrics"] or {}
        lines.append(
            f"| [{row['id']}]({row['url']}) | {row['category']} | {'saved' if row['accepted'] else 'unavailable'} | {m.get('words', '—')} | {m.get('link_count', '—')} | {', '.join(row['flags']) or 'none'} |"
        )
    (root / "AUDIT.md").write_text("\n".join(lines) + "\n")
    print(f"{sum(r['accepted'] for r in rows)}/{len(rows)} actual files downloaded; audit written")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "audit"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.command == "fetch":
        asyncio.run(fetch_corpus(args.root, args.refresh))
    audit(args.root)


if __name__ == "__main__":
    main()
