"""Frozen first-pass clarification and branched response evaluations."""

from __future__ import annotations

import argparse
import copy
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

from brief.benchmark import fingerprint
from brief.contracts import GenerationInput, validate_result
from brief.corpus import write_json
from brief.generation import build_request, render_guide
from brief.model import OpenAIGenerator

if TYPE_CHECKING:
    from brief.interfaces import Completer


def matching_question(case: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any] | None:
    pattern = case.get("ambiguity_pattern")
    return next(
        (q for q in raw.get("questions", []) if pattern and re.search(pattern, q["question"], re.IGNORECASE)), None
    )


def grade(
    case: dict[str, Any],
    context: dict[str, Any],
    raw: dict[str, Any],
    stage: str,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failures = []
    try:
        result = validate_result(raw, GenerationInput.model_validate(context))
    except ValueError as error:
        return {"passed": False, "failures": [str(error)], "markdown": None}
    document = render_guide(result.guide, GenerationInput.model_validate(context).sources) if result.guide else None
    if stage == "first":
        question = matching_question(case, raw)
        if case["expect_question"] and not question:
            failures.append("Missing question about consequential ambiguity")
        if not case["expect_question"] and result.questions:
            failures.append("Unnecessary clarification on a defaultable case")
        if question:
            if question["recommendedOption"] is None:
                failures.append("No recommendation supplied")
            if len({o.casefold().strip() for o in question["options"]}) != len(question["options"]):
                failures.append("Duplicate options")
            if len(question["rationale"].split()) < 6:
                failures.append("Rationale too terse to explain the consequence")
    if stage in {"recommended", "alternative", "custom", "dismissed", "more"} and matching_question(case, raw):
        failures.append("Repeated answered or dismissed ambiguity")
    expected = expected or {}
    links = {l.source_id for s in result.guide.sections for l in s.links} if result.guide else set()
    for id in expected.get("include", []):
        if id not in links:
            failures.append(f"Requested resource absent: {id}")
    for id in expected.get("exclude", []):
        if id in links:
            failures.append(f"Excluded resource retained: {id}")
    pattern = expected.get("document_pattern")
    if pattern and not re.search(pattern, document or "", re.IGNORECASE):
        failures.append("Owner answer not reflected in document")
    if pattern and expected.get("kind") == "fact" and result.guide:
        claims = ([result.guide.summary] if result.guide.summary else []) + result.guide.context
        if not any(re.search(pattern, c.text, re.IGNORECASE) and "answer" in c.evidence_ids for c in claims):
            failures.append("Owner fact missing decision provenance")
    forbidden = expected.get("removed_forbidden") if stage == "removed" else None
    if forbidden and re.search(forbidden, document or "", re.IGNORECASE):
        failures.append("Removed owner fact persisted")
    return {
        "passed": not failures,
        "failures": failures,
        "markdown": document,
        "caution": "Mechanical checks do not prove question usefulness, option quality, or semantic compliance.",
    }


def branches(case: dict[str, Any], first: dict[str, Any]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Use the actual frozen question/options; never pass previous generated text as authority."""
    question = matching_question(case, first)
    if not question:
        return []
    base = copy.deepcopy(case["input"])
    base["dismissedTopics"] += [q["topic"] for q in first["questions"]]
    base["mode"] = "generate"
    recommended = question["recommendedOption"]
    rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    choices = (
        [("alternative", 0)]
        if recommended is None
        else [("recommended", recommended), ("alternative", (recommended + 1) % len(question["options"]))]
    )
    for stage, index in choices:
        context = copy.deepcopy(base)
        statement = question["question"] + " Answer: " + question["options"][index]
        context["decisions"].append({"id": "answer", "kind": "preference", "statement": statement, "active": True})
        rows.append((stage, context, {}))
    custom = case.get("custom")
    if custom:
        context = copy.deepcopy(base)
        context["decisions"].append(
            {
                "id": "answer",
                "kind": custom["kind"],
                "statement": question["question"] + " Answer: " + custom["statement"],
                "active": True,
            }
        )
        rows.append(("custom", context, custom))
        removed = copy.deepcopy(context)
        removed["decisions"][-1]["active"] = False
        removed["dismissedTopics"] = case["input"]["dismissedTopics"][:]
        rows.append(("removed", removed, {"removed_forbidden": custom.get("removed_forbidden")}))
        more = copy.deepcopy(context)
        more.update(mode="questions", maxQuestions=1)
        rows.append(("more", more, {}))
    rows.append(("dismissed", copy.deepcopy(base), {}))
    return rows


def complete(
    case: dict[str, Any],
    stage: str,
    context: dict[str, Any],
    expected: dict[str, Any],
    generator: Completer,
    out: Path,
    parent: str | None = None,
) -> dict[str, Any]:
    request = build_request(GenerationInput.model_validate(context))
    row: dict[str, Any] = {
        "case_id": case["id"],
        "stage": stage,
        "case_sha256": fingerprint(case),
        "request": request,
        "request_sha256": fingerprint(request),
        "parent_response_sha256": parent,
    }
    try:
        completion = generator.complete(request)
        row.update(
            response=completion.raw,
            metadata=completion.metadata,
            grade=grade(case, context, completion.raw, stage, expected),
        )
    except ValueError as error:
        row.update(response=None, grade={"passed": False, "failures": [str(error)], "markdown": None})
    write_json(out / f"{case['id']}--{stage}.json", row)
    if row["grade"].get("markdown") is not None:
        (out / f"{case['id']}--{stage}.llms.txt").write_text(row["grade"]["markdown"])
    print(case["id"], stage, row["grade"]["passed"], flush=True)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--first-dir", type=Path, help="Branch from immutable first-pass outputs; otherwise capture first passes only"
    )
    parser.add_argument("--cases", type=Path, default=Path("evals/corpus/dialogue-cases.json"))
    parser.add_argument("--regrade", type=Path, help="Regrade saved artifacts without model/network calls")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Use a fresh output directory")
    args.out.mkdir(parents=True)
    cases = json.loads(args.cases.read_text())
    if args.regrade:
        by_id = {case["id"]: case for case in cases}
        rows = []
        for path in sorted(args.regrade.glob("*--*.json")):
            row = json.loads(path.read_text())
            case = by_id[row["case_id"]]
            if row["case_sha256"] != fingerprint(case):
                raise ValueError("Case changed; preserve labels or explicitly migrate artifacts")
            expected = case.get("custom") or {} if row["stage"] == "custom" else {}
            if row["stage"] == "removed":
                expected = {"removed_forbidden": (case.get("custom") or {}).get("removed_forbidden")}
            row["original_grade"] = row["grade"]
            row["grade"] = grade(case, json.loads(row["request"]["user"]), row["response"], row["stage"], expected)
            write_json(args.out / path.name, row)
            rows.append(row)
        if not rows:
            parser.error("No saved artifacts found")
        write_json(
            args.out / "report.json",
            {"results": rows, "passed": sum(r["grade"]["passed"] for r in rows), "total": len(rows)},
        )
        return
    generator = OpenAIGenerator()

    def run(case: dict[str, Any]) -> list[dict[str, Any]]:
        if not args.first_dir:
            return [complete(case, "first", case["input"], {}, generator, args.out)]
        first = json.loads((args.first_dir / f"{case['id']}--first.json").read_text())
        if first["case_sha256"] != fingerprint(case):
            raise ValueError("First-pass case changed; capture new first passes")
        if not first["response"] or not matching_question(case, first["response"]):
            return [
                {
                    "case_id": case["id"],
                    "stage": "blocked" if case["expect_question"] else "not_applicable",
                    "grade": {
                        "passed": not case["expect_question"],
                        "failures": ["No target question to answer"] if case["expect_question"] else [],
                    },
                }
            ]
        return [
            complete(case, stage, context, expected, generator, args.out, fingerprint(first["response"]))
            for stage, context, expected in branches(case, first["response"])
        ]

    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = [row for group in pool.map(run, cases) for row in group]
    write_json(
        args.out / "report.json",
        {"results": rows, "passed": sum(r["grade"]["passed"] for r in rows), "total": len(rows)},
    )


if __name__ == "__main__":
    main()
