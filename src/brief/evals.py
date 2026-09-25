"""Local provider-neutral evaluator. Gold labels never enter exported model requests."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from brief.contracts import GenerationInput, validate_result
from brief.generation import PROMPT_VERSION, build_request, render_guide


def grade(case: dict[str, Any], raw: object) -> dict[str, Any]:
    failures: list[str] = []
    markdown = None
    try:
        context = GenerationInput.model_validate(case["input"])
        result = validate_result(raw, context)
        expected = case["expected"]
        ids = [link.source_id for section in result.guide.sections for link in section.links] if result.guide else []
        failures.extend(f"Missing required resource: {id}" for id in expected["include"] if id not in ids)
        failures.extend(f"Unwanted resource: {id}" for id in expected["exclude"] if id in ids)
        if expected.get("firstSource") and ids[:1] != [expected["firstSource"]]:
            failures.append("Audience ordering not respected")
        text = result.model_dump_json().lower()
        failures.extend(f"Forbidden text: {phrase}" for phrase in expected["forbidden"] if phrase.lower() in text)
        if len(result.questions) < expected.get("minQuestions", 0):
            failures.append("Missing consequential question")
        if len(result.questions) > expected.get("maxQuestions", context.max_questions):
            failures.append("Unnecessary questions")
        if case["id"] == "user-fact" and not (
            result.guide
            and any("launch" in c.evidence_ids and "October 1, 2026" in c.text for c in result.guide.context)
        ):
            failures.append("Missing user fact with decision provenance")
        if result.guide:
            markdown = render_guide(result.guide, context.sources)
    except (ValueError, KeyError) as error:
        failures.append(str(error))
    return {"passed": not failures, "failures": failures, "markdown": markdown}


def invoke(command: str, request: dict[str, Any], timeout: float = 90) -> object:
    # Use temporary files to avoid accumulating unbounded adapter output in memory.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        completed = subprocess.run(
            [str(Path(command).resolve())],
            input=json.dumps(request).encode(),
            stdout=stdout,
            stderr=stderr,
            timeout=timeout,
            check=False,
        )
        if completed.returncode:
            raise ValueError(
                f"Adapter exited {completed.returncode}; inspect adapter logs (stderr not saved to avoid secrets)"
            )
        if stdout.tell() > 1_000_000:
            raise ValueError("Adapter response exceeds 1 MB")
        stdout.seek(0)
        return json.load(stdout)


def metadata_baseline(context: GenerationInput) -> dict[str, Any]:
    """Intentionally naive control. Never receives or consults gold expectations."""
    return {
        "guide": None
        if context.mode == "questions"
        else {
            "title": context.sources[0].title if context.sources else "Website",
            "summary": None,
            "context": [],
            "sections": [
                {
                    "title": "Resources",
                    "links": [
                        {"sourceId": s.id, "label": s.title, "description": s.description or None}
                        for s in context.sources
                    ],
                }
            ]
            if context.sources
            else [],
        },
        "explanation": "Metadata-only baseline; no reasoning model used.",
        "questions": [],
    }


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--export", type=Path)
    modes.add_argument("--responses", type=Path)
    modes.add_argument("--adapter", help="Executable receiving one JSON request on stdin")
    modes.add_argument("--baseline", action="store_true")
    modes.add_argument("--openai", action="store_true", help="Run the OpenAI adapter with usage metadata")
    parser.add_argument("--cases", type=Path, default=Path("evals/cases.json"))
    parser.add_argument("--out", type=Path, default=Path(f"evals/results/{time.time_ns()}"))
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    ids = [case["id"] for case in cases]
    if not ids or len(set(ids)) != len(ids) or any(not id.replace("-", "").isalnum() for id in ids):
        parser.error("Cases need unique, filename-safe IDs and at least one case")
    out = (args.export or args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    results = []
    generator = None
    if args.openai:
        from brief.model import OpenAIGenerator

        generator = OpenAIGenerator()
    for case in cases:
        context = GenerationInput.model_validate(case["input"])
        request = build_request(context)
        if args.export:
            write_json(out / f"{case['id']}.json", request)
            continue
        started = time.monotonic()
        raw = None
        metadata = None
        try:
            if args.responses:
                raw = json.loads((args.responses / f"{case['id']}.json").read_text())
            elif generator:
                completion = generator.complete(request)
                raw, metadata = completion.raw, completion.metadata
            elif args.adapter:
                raw = invoke(args.adapter, request)
            else:
                raw = metadata_baseline(context)
            result = grade(case, raw)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            result = {"passed": False, "failures": [str(error)], "markdown": None}
        duration_ms = round((time.monotonic() - started) * 1000)
        write_json(
            out / f"{case['id']}.json",
            {
                "request": request,
                "response": raw,
                "result": result,
                "durationMs": duration_ms,
                "modelMetadata": metadata,
            },
        )
        if result["markdown"] is not None:
            (out / f"{case['id']}.llms.txt").write_text(result["markdown"])
        results.append(
            {
                "id": case["id"],
                **{k: v for k, v in result.items() if k != "markdown"},
                "durationMs": duration_ms,
                "modelMetadata": metadata,
            }
        )
        print(f"{'PASS' if result['passed'] else 'FAIL'} {case['id']}: {'; '.join(result['failures'])}", flush=True)
    if args.export:
        print(f"Exported {len(cases)} requests without gold expectations to {out}")
        return 0
    write_json(
        out / "report.json",
        {
            "promptVersion": PROMPT_VERSION,
            "mode": "metadata-baseline"
            if args.baseline
            else "replay"
            if args.responses
            else "openai"
            if args.openai
            else "adapter",
            "evaluation": "deterministic-checks-only",
            "adapterInvoked": bool(args.adapter or args.openai),
            "humanReviewCompleted": False,
            "results": results,
        },
    )
    (out / "review.md").write_text(
        "# Human review\n\nRecord provider/model/settings. Check each response against its request. "
        "Passing deterministic checks does not prove factual accuracy.\n\n"
        "Score 0 (bad), 1 (mixed), 2 (good): factual entailment, resource usefulness, decision fidelity, "
        "question value, concision. Cite evidence for deductions.\n\n"
        + "\n".join(
            f"## {c['id']}\n\n{c['description']}\n\nScores: pending\nEvidence / notes: pending\n" for c in cases
        )
    )
    passed = sum(r["passed"] for r in results)
    print(f"{passed}/{len(results)} deterministic cases passed. Artifacts: {out}")
    return int(passed != len(results))


if __name__ == "__main__":
    raise SystemExit(main())
