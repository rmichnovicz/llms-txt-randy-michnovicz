"""Preserve original judge outputs while correcting literal-JSON quote validation."""

import json
from pathlib import Path

from brief.corpus import write_json
from brief.dialogue_review import anchored_quote

for run in ["dialogue-review-v1", "dialogue-review-controls-v1"]:
    root = Path("evals/reports") / run
    target = root / "anchors-reviewed.json"
    if target.exists():
        raise SystemExit("Use a fresh report path")
    rows = []
    for path in sorted(root.glob("*.json")):
        if path.name == "report.json":
            continue
        row = json.loads(path.read_text())
        artifacts = row.get("candidate_artifacts")
        if artifacts is None:
            id = row["case_id"]
            paths = [Path("evals/corpus/dialogue-first-v1") / f"{id}--first.json"] + list(
                Path("evals/results/dialogue-follow-v1").glob(f"{id}--*.json")
            )
            artifacts = [json.loads(p.read_text()) for p in paths]
        outputs = {r["stage"]: r["response"] for r in artifacts}
        row["original_anchor_errors"] = row["anchor_errors"]
        row["anchor_errors"] = [
            i for i in row["judgment"]["issues"] if not anchored_quote(i["quote"], outputs.get(i["stage"]))
        ]
        if row.get("control"):
            scores = row["judgment"]["scores"]
            dimension = {
                "irrelevant-duplicate-question": "question_value",
                "ignored-owner-answer": "answer_fidelity",
            }.get(row["control"])
            row["control_passed"] = not row["anchor_errors"] and (
                scores[dimension] < 2 if dimension else all(v == 2 for v in scores.values())
            )
        rows.append(row)
    write_json(
        target, {"source_run": run, "results": rows, "anchor_failures": sum(bool(r["anchor_errors"]) for r in rows)}
    )
    print(run, len(rows), "reviews;", sum(bool(r["anchor_errors"]) for r in rows), "anchor failures")
