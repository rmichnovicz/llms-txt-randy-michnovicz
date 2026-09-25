"""Regrade saved reader traces without model or network calls; never overwrite raw runs."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from brief.consumer_eval import canonical, grade_answer
from brief.corpus import write_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("run", type=Path)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
if args.out.exists():
    parser.error("Use a fresh report path")
tasks = {t["id"]: t for t in json.loads(Path("evals/corpus/consumer-tasks.json").read_text())}
rows = []
for path in sorted(args.run.glob("*--*.json")):
    row = json.loads(path.read_text())
    observed = {}
    for page in row["observations"]:
        if page.get("content") and not page.get("is_navigation_guide"):
            observed[canonical(page["url"])] = page
    for step in row["trace"]:
        fetch = step.get("fetch", {})
        if fetch.get("url") and not fetch.get("error") and canonical(fetch["url"]) in observed:
            observed[canonical(step["action"]["url"])] = observed[canonical(fetch["url"])]
    row["original_grade"] = row["grade"]
    row["grade"] = grade_answer(tasks[row["task_id"]], row["final"], observed)
    if row["errors"]:
        row["grade"]["answer_correct"] = row["grade"]["grounded_success"] = False
    rows.append(row)
groups = defaultdict(list)
for row in rows:
    groups[row["arm"]].append(row)
summary = {
    arm: {
        "trials": len(rs),
        "known_fact_coverage": sum(r["grade"]["answer_correct"] for r in rs),
        "verified_citation_success": sum(r["grade"]["grounded_success"] for r in rs),
        "opens": sum(r["opens"] for r in rs),
        "input_tokens": sum(u.get("input_tokens", 0) for r in rs for u in r["usage"]),
        "output_tokens": sum(u.get("output_tokens", 0) for r in rs for u in r["usage"]),
        "fetch_errors": sum(bool(s.get("fetch", {}).get("error")) for r in rs for s in r["trace"]),
    }
    for arm, rs in groups.items()
}
write_json(args.out, {"source_run": str(args.run), "summary": summary, "results": rows})
print(json.dumps(summary, indent=2))
