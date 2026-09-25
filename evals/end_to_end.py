"""Replay authored HTTP sites through production crawl, generation and Markdown rendering."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from brief.contracts import GenerationInput, validate_result
from brief.corpus import parse_file, write_json
from brief.crawl.fetch import Response
from brief.crawl.runner import crawl
from brief.evals import invoke, metadata_baseline
from brief.generation import PROMPT_VERSION, SYSTEM_PROMPT, build_request, render_guide
from brief.interfaces import URLPolicy

CORPUS = Path(__file__).with_name("end_to_end_sites.json")


class FrozenFetcher:
    """No sockets: unknown fixture URLs return 404, and scope policy is still enforced."""

    interval = 0.0

    def __init__(self, case: dict[str, Any]) -> None:
        self.responses = {urljoin(case["url"], path): item for path, item in case["responses"].items()}
        self.requests: list[str] = []

    async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
        verdict = allowed(url)
        if not (await verdict if inspect.isawaitable(verdict) else verdict):
            raise ValueError("Fixture request violates crawler scope")
        self.requests.append(url)
        item = self.responses.get(url, {"status": 404, "content_type": "text/plain", "body": ""})
        return Response(url, item.get("status", 200), item.get("content_type", "text/html"), item["body"].encode())


def coverage(expected: set[str], observed: set[str]) -> dict[str, Any]:
    matched = expected & observed
    return {
        "matched": len(matched),
        "total": len(expected),
        "ratio": len(matched) / len(expected) if expected else None,
        "missing": sorted(expected - observed),
    }


def measure(important: set[str], usable: set[str], linked: set[str]) -> dict[str, Any]:
    return {
        "crawl_important_coverage": coverage(important, usable),
        "generated_important_coverage": coverage(important, linked),
        "generated_usable_source_coverage": coverage(usable, linked),
        "generated_link_precision": coverage(linked, usable),
        "unsupported_destinations": sorted(linked - usable),
    }


async def run_case(case: dict[str, Any], output: Path, *, adapter: str | None = None) -> dict[str, Any]:
    output.mkdir()
    started = time.monotonic()
    fetcher = FrozenFetcher(case)
    result = await crawl(case["url"], fetcher=fetcher, max_pages=case.get("max_pages", 12), deadline=30)
    write_json(output / "crawl.json", result.as_dict())
    write_json(output / "requests.json", fetcher.requests)
    context = GenerationInput(
        site_url=case["url"],
        sources=result.sources,
        decisions=[],
        dismissed_topics=[],
        mode="generate",
        max_questions=0,
    )
    request = build_request(context)
    write_json(output / "request.json", request)
    error = None
    linked: set[str] = set()
    generation_started = time.monotonic()
    try:
        raw = await asyncio.to_thread(invoke, adapter, request) if adapter else metadata_baseline(context)
        write_json(output / "response.json", raw)
        generated = validate_result(raw, context)
        assert generated.guide is not None
        markdown = render_guide(generated.guide, result.sources)
        (output / "llms.txt").write_text(markdown)
        linked = {link["url"] for link in parse_file(markdown, case["url"])["links"]}
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
        # The adapter already sanitizes execution failures; retain invalid outputs above for inspection.
        error = {"type": type(exc).__name__, "message": str(exc)[:2000]}
    important = {urljoin(case["url"], path) for path in case["important_paths"]}
    usable = {source.markdown_url or source.url for source in result.sources}
    row = {
        "id": case["id"],
        "category": case["category"],
        "notes": case["notes"],
        "metrics": measure(important, usable, linked),
        "generation_error": error,
        "crawl_warnings": result.warnings,
        "crawl_stop_reason": result.stop_reason,
        "crawl_truncated": result.truncated,
        "crawl_duration_ms": result.duration_ms,
        "generation_duration_ms": round((time.monotonic() - generation_started) * 1000),
        "total_duration_ms": round((time.monotonic() - started) * 1000),
    }
    write_json(output / "result.json", row)
    return row


async def run(corpus: Path, output: Path, *, adapter: str | None = None) -> dict[str, Any]:
    payload = corpus.read_bytes()
    cases = json.loads(payload)
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)) or any(Path(id).name != id or id in {".", ".."} for id in ids):
        raise ValueError("Case IDs must be unique directory names")
    output.mkdir(parents=True, exist_ok=False)
    (output / "corpus.json").write_bytes(payload)
    rows = [await run_case(case, output / case["id"], adapter=adapter) for case in cases]
    summary: dict[str, Any] = {
        "cases": len(rows),
        "generation_errors": sum(r["generation_error"] is not None for r in rows),
    }
    for metric in (
        "crawl_important_coverage",
        "generated_important_coverage",
        "generated_usable_source_coverage",
        "generated_link_precision",
    ):
        matched = sum(row["metrics"][metric]["matched"] for row in rows)
        total = sum(row["metrics"][metric]["total"] for row in rows)
        summary[metric] = {"matched": matched, "total": total, "ratio": matched / total if total else None}
    root = Path(__file__).resolve().parents[1]
    revision, status = await asyncio.gather(
        *(
            asyncio.to_thread(subprocess.run, command, cwd=root, capture_output=True, text=True, check=False)
            for command in (["git", "rev-parse", "HEAD"], ["git", "status", "--porcelain"])
        )
    )
    code_files = [Path(__file__), *sorted((root / "src" / "brief").rglob("*.py")), root / "uv.lock"]
    report = {
        "mode": "model-adapter" if adapter else "metadata-baseline",
        "corpus_sha256": hashlib.sha256(payload).hexdigest(),
        "prompt_version": PROMPT_VERSION,
        "git_revision": revision.stdout.strip() if revision.returncode == 0 else None,
        "git_dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
        "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        "code_sha256": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in code_files
        },
        "limitations": [
            "Authored synthetic HTTP fixtures; no live network, DNS, redirect transport, JavaScript rendering, or browser UI.",
            "Replay omits model-guided coverage assessment, durable jobs, persistence, and browser flows.",
            "Baseline is the existing metadata-only control, not production model quality; it links every extracted source.",
            "Coverage is URL set overlap, not semantic accuracy, useful curation, factual entailment, or task success.",
            "Empty denominators are null. Aggregate ratios are micro-averages; failed and blocked cases remain included.",
            "Replay timings are diagnostic only; they do not measure live-site latency.",
        ],
        "summary": summary,
        "results": rows,
    }
    write_json(output / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--baseline", action="store_true", help="Explicit offline metadata control; no model or API calls"
    )
    mode.add_argument("--adapter", help="Existing brief-eval executable protocol; may spend API credits")
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--out", type=Path, required=True, help="Fresh directory for complete replay evidence")
    args = parser.parse_args()
    report = asyncio.run(run(args.corpus, args.out, adapter=args.adapter))
    print(json.dumps(report["summary"], indent=2))
    if report["summary"]["generation_errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
