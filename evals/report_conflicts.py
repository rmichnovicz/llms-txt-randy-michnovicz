"""Review conflict outputs against corrected editorial labels without rewriting raw evidence."""

import json
from pathlib import Path

from brief.benchmark import fingerprint, grade_generation
from brief.corpus import write_json

root = Path("evals/corpus/conflict-pilot-v1")
out = Path("evals/reports/conflict-pilot-reviewed.json")
if out.exists():
    raise SystemExit("Reviewed report already exists")
cases = {c["id"]: c for c in json.loads(Path("evals/corpus/conflict-cases.json").read_text())}
rows = []
for path in sorted(root.glob("*--r1.json")):
    row = json.loads(path.read_text())
    row["original_result"] = row["result"]
    row["reviewed_case_sha256"] = fingerprint(cases[row["caseId"]])
    row["result"] = grade_generation(cases[row["caseId"]], row["response"])
    rows.append(row)
write_json(
    out,
    {
        "label_correction": "Resource selection is not conflict correctness: removed an unrelated requirement to link both homepage and policy from every draft.",
        "passed": sum(r["result"]["passed"] for r in rows),
        "total": len(rows),
        "results": rows,
    },
)
print(sum(r["result"]["passed"] for r in rows), "/", len(rows))
