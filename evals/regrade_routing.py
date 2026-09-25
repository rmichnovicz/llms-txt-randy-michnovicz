from typing import Any

"""Regrade saved model choices after a documented gold-label correction, without new calls."""

import argparse
import json
from pathlib import Path

from brief.corpus import parse_file, write_json
from brief.routing_eval import grade_routing

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
if args.out.exists():
    parser.error("Use a fresh output directory")
args.out.mkdir(parents=True)
root = Path("evals/corpus")
tasks = {t["id"]: t for t in json.loads((root / "routing-tasks.json").read_text())}
old = json.loads((args.run / "report.json").read_text())
rows = []
for row in old["results"]:
    meta = json.loads((root / "metadata" / f"{row['file_id']}.json").read_text())
    if meta["sha256"] != row["file_sha256"]:
        raise ValueError("Frozen file changed")
    text = (root / meta["raw_path"]).read_text(encoding="utf-8-sig", errors="replace")[: row["visible_chars"]]
    parsed = parse_file(text, meta["final_url"])
    row["original_result"] = row["result"]
    row["acceptable_urls"] = tasks[row["id"]]["acceptable_urls"]
    row["result"] = grade_routing(tasks[row["id"]], row["urls"], parsed["links"] + parsed["bare_links"])
    write_json(args.out / f"{row['id']}.json", row)
    rows.append(row)
summary: dict[str, Any] = {
    "tasks": len(rows),
    "passed": sum(r["result"]["passed"] for r in rows),
    "top1": sum(r["result"]["top1"] for r in rows),
    "top3": sum(r["result"]["top3"] for r in rows),
    "gold_outside_budget": sum(r["result"]["gold_visible"] is False for r in rows),
    "mean_reciprocal_rank": sum(r["result"]["reciprocal_rank"] for r in rows) / len(rows),
}
write_json(
    args.out / "report.json",
    {
        "mode": old["mode"],
        "budget_chars": old["budget_chars"],
        "regraded_from": str(args.run),
        "summary": summary,
        "results": rows,
    },
)
print(json.dumps(summary, indent=2))
