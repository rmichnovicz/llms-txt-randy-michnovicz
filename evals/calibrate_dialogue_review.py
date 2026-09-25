"""Small positive/negative controls for the advisory dialogue reviewer."""

from __future__ import annotations

import copy
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from openai import OpenAI

from brief.corpus import write_json
from brief.dialogue_review import review

out = Path("evals/reports/dialogue-review-controls-v1")
if out.exists():
    raise SystemExit("Use a fresh controls report directory")
out.mkdir(parents=True)
case = json.loads(Path("evals/corpus/dialogue-cases.json").read_text())[0]
first = json.loads(Path("evals/corpus/dialogue-first-v1/undated-interest-conflict--first.json").read_text())
custom = json.loads(Path("evals/results/dialogue-follow-v1/undated-interest-conflict--custom.json").read_text())
controls: list[tuple[str, list[dict[str, Any]], str | None]] = []
controls.append(("grounded-positive", [first, custom], None))
filler = copy.deepcopy(first)
filler["response"]["questions"] = [
    {
        "topic": "favorite-color",
        "question": "What is your favorite color?",
        "rationale": "A favorite color is necessary to determine the correct current financial rate.",
        "evidenceIds": ["home"],
        "options": ["Blue", "Blue"],
        "recommendedOption": 0,
    }
]
controls.append(("irrelevant-duplicate-question", [filler], "question_value"))
ignored = copy.deepcopy(custom)
ignored["response"]["guide"]["context"] = [
    {"text": "The verified current annual interest rate is 9.9%.", "evidenceIds": ["answer"]}
]
controls.append(("ignored-owner-answer", [first, ignored], "answer_fidelity"))
client = OpenAI(timeout=90, max_retries=0)


def run(control: tuple[str, list[dict[str, Any]], str | None]) -> dict[str, Any]:
    name, artifacts, bad_dimension = control
    row = review(case, artifacts, client, os.environ.get("OPENAI_MODEL", "gpt-6-sol"))
    row["control"] = name
    scores = row.get("judgment", {}).get("scores", {})
    row["control_passed"] = (
        bool(scores)
        and not row.get("anchor_errors")
        and (scores[bad_dimension] < 2 if bad_dimension else all(v == 2 for v in scores.values()))
    )
    row["candidate_artifacts"] = artifacts
    write_json(out / (name + ".json"), row)
    print(name, row["control_passed"], flush=True)
    return row


with ThreadPoolExecutor(max_workers=3) as pool:
    rows = list(pool.map(run, controls))
write_json(out / "report.json", {"results": rows, "passed": sum(r["control_passed"] for r in rows)})
