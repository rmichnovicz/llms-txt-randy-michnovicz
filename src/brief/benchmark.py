"""Repeated, stratified generator benchmark over frozen, versioned evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from brief.contracts import GenerationInput
from brief.corpus import write_json
from brief.evals import grade, metadata_baseline
from brief.generation import build_request

if TYPE_CHECKING:
    from brief.interfaces import Completer


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def grade_generation(case: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    # Existing exact schema/evidence-ID checks are necessary but do not prove entailment.
    import re

    result = grade(case, raw)
    failures = result["failures"]
    if result["markdown"] is not None:
        document = result["markdown"]
        expected = case["expected"]
        links = [x for s in raw["guide"]["sections"] for x in s["links"]]
        if len(links) > expected.get("maxLinks", 10000):
            failures.append("Document exceeds requested link budget")
        if len(document.split()) > expected.get("maxWords", 100000):
            failures.append("Document exceeds requested word budget")
        for phrase in expected.get("forbiddenDocument", []):
            if phrase.lower() in document.lower():
                failures.append(f"Unsupported/forbidden document claim: {phrase}")
        if expected.get("documentPattern") and not re.search(expected["documentPattern"], document, re.IGNORECASE):
            failures.append("Document language/content requirement missing")
        for source_id, pattern in expected.get("qualifiedResources", {}).items():
            for section in raw["guide"]["sections"]:
                for link in section["links"]:
                    if link["sourceId"] == source_id and not re.search(
                        pattern,
                        section["title"] + " " + link["label"] + " " + (link["description"] or ""),
                        re.IGNORECASE,
                    ):
                        failures.append("Archived/versioned resource lacks an explicit qualifier")
        claim = expected.get("requiredClaim")
        claims = ([raw["guide"]["summary"]] if raw["guide"]["summary"] else []) + raw["guide"]["context"]
        if claim and not any(claim["text"] in c["text"] and claim["evidenceId"] in c["evidenceIds"] for c in claims):
            failures.append("Required user fact lacks its decision provenance")
    pattern = case["expected"].get("questionPattern")
    if (
        pattern
        and isinstance(raw, dict)
        and isinstance(raw.get("questions"), list)
        and not any(
            isinstance(q, dict)
            and isinstance(q.get("question"), str)
            and re.search(pattern, q["question"], re.IGNORECASE)
            for q in raw["questions"]
        )
    ):
        failures.append("Question does not address the known ambiguity")
    result["passed"] = not failures
    return result


def load_cases() -> list[dict[str, Any]]:
    legacy = json.loads(Path("evals/cases.json").read_text())
    for c in legacy:
        c.update(kind="legacy-authored", category="mixed", split="development")
    return legacy + [
        case
        for name in ["authored-generation-cases.json", "real-generation-cases.json"]
        for case in json.loads(Path("evals/corpus", name).read_text())
    ]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    usage = [r["modelMetadata"].get("usage") or {} for r in rows if r.get("modelMetadata")]
    latency = [r["durationMs"] for r in rows]
    grouped = defaultdict(list)
    for r in rows:
        grouped[r["caseId"]].append(r["result"]["passed"])
    groups: dict[str, Any] = {}
    for dimension in ["category", "kind", "split"]:
        groups[dimension] = {}
        for value in sorted({r[dimension] for r in rows}):
            selected = [r for r in rows if r[dimension] == value]
            groups[dimension][value] = {
                "attempts": len(selected),
                "passed": sum(r["result"]["passed"] for r in selected),
            }
    return {
        "attempts": len(rows),
        "passed": sum(r["result"]["passed"] for r in rows),
        "cases": len(grouped),
        "consistently_passing_cases": sum(all(v) for v in grouped.values()),
        "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
        "output_tokens": sum(u.get("output_tokens", 0) for u in usage),
        "latency_ms_median": statistics.median(latency) if latency else None,
        "latency_ms_p95": sorted(latency)[min(len(latency) - 1, int(len(latency) * 0.95))] if latency else None,
        "groups": groups,
    }


def run_case(
    case: dict[str, Any],
    repeat: int,
    out: Path,
    mode: str,
    prompt: dict[str, Any] | None = None,
    replay: Path | None = None,
    generator: Completer | None = None,
) -> dict[str, Any]:
    context = GenerationInput.model_validate(case["input"])
    request = build_request(context)
    if prompt:
        request.update(system=prompt["system"], promptVersion=prompt["promptVersion"])
    id = f"{case['id']}--r{repeat}"
    raw, metadata = None, None
    start = time.monotonic()
    try:
        if mode == "openai":
            if generator is None:
                raise ValueError("OpenAI mode requires a generator")
            completion = generator.complete(request)
            raw, metadata = completion.raw, completion.metadata
        elif mode == "replay":
            if replay is None:
                raise ValueError("Replay mode requires a directory")
            saved = json.loads((replay / f"{id}.json").read_text())
            if saved["request_sha256"] != fingerprint(request):
                raise ValueError("Replay request differs: use the original prompt and unchanged model evidence")
            raw = saved["response"]
        else:
            raw = metadata_baseline(context)
        result = grade_generation(case, raw)
    except (ValueError, OSError) as error:
        result = {"passed": False, "failures": [str(error)[:500]], "markdown": None}
    row: dict[str, Any] = {
        "id": id,
        "caseId": case["id"],
        "repeat": repeat,
        "category": case["category"],
        "kind": case["kind"],
        "split": case["split"],
        "case_sha256": fingerprint(case),
        "request_sha256": fingerprint(request),
        "request": request,
        "response": raw,
        "result": result,
        "modelMetadata": metadata,
        "durationMs": round((time.monotonic() - start) * 1000),
    }
    write_json(out / f"{id}.json", row)
    if result["markdown"] is not None:
        (out / f"{id}.llms.txt").write_text(result["markdown"])
    print(f"{'PASS' if result['passed'] else 'FAIL'} {id}: {'; '.join(result['failures'])[:240]}", flush=True)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["baseline", "openai", "replay"], required=True)
    parser.add_argument("--split", choices=["development", "holdout", "all"], default="development")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--max-calls", type=int, default=250)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text()) if args.cases else load_cases()
    cases = [c for c in cases if args.split == "all" or c["split"] == args.split]
    if not cases or args.repeats < 1 or not 1 <= args.workers <= 8 or len(cases) * args.repeats > args.max_calls:
        parser.error("Empty corpus, invalid limits, or max-calls exceeded")
    if args.mode == "replay" and not args.replay:
        parser.error("--replay is required in replay mode")
    if args.out.exists():
        parser.error("Use a new output directory; existing evidence must not be overwritten")
    args.out.mkdir(parents=True)
    prompt = json.loads(args.prompt.read_text()) if args.prompt else None
    generator = None
    if args.mode == "openai":
        from brief.model import OpenAIGenerator

        generator = OpenAIGenerator()
    write_json(
        args.out / "run.json",
        {
            "mode": args.mode,
            "split": args.split,
            "repeats": args.repeats,
            "corpus_sha256": fingerprint(cases),
            "case_count": len(cases),
            "started_at": datetime.now(UTC).isoformat(),
            "workers": args.workers,
            "prompt_override": str(args.prompt) if args.prompt else None,
        },
    )
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(run_case, c, r, args.out, args.mode, prompt, args.replay, generator)
            for c in cases
            for r in range(1, args.repeats + 1)
        ]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda r: r["id"])
    summary = summarize(rows)
    write_json(
        args.out / "report.json",
        {
            "summary": summary,
            "evaluation": "deterministic invariants and editorial expectations; not a factual accuracy score",
            "human_review_completed": False,
            "results": [{k: v for k, v in r.items() if k not in ["request", "response"]} for r in rows],
        },
    )
    print(json.dumps(summary, indent=2))
    return int(summary["passed"] != summary["attempts"])


if __name__ == "__main__":
    raise SystemExit(main())
