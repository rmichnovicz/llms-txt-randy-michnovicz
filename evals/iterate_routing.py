from typing import Any

"""Controlled file edit: move a real contact route before the context cutoff."""

import json
import os
from pathlib import Path

from openai import OpenAI

from brief.corpus import digest, parse_file, write_json
from brief.routing_eval import grade_routing, model_route

root = Path("evals/corpus")
meta = json.loads((root / "metadata/wheelhouse.json").read_text())
text = (root / meta["raw_path"]).read_text()
lines = text.splitlines()
contact = [line for line in lines if "](https://www.wheelhousedmg.com/contact/)" in line]
assert len(contact) == 1
rest = [line for line in lines if line not in contact]
insert = next(i for i, line in enumerate(rest) if line.startswith("## "))
rest[insert:insert] = ["## Contact", "", contact[0], ""]
modified = "\n".join(rest) + "\n"
variant = root / "variants/wheelhouse-contact-first.txt"
variant.parent.mkdir(parents=True, exist_ok=True)
variant.write_text(modified)
write_json(
    variant.with_suffix(".json"),
    {
        "kind": "analyst-derived-variant",
        "parent": "wheelhouse",
        "parent_sha256": meta["sha256"],
        "sha256": digest(modified.encode()),
        "change": "Move the existing contact link into a short first section; preserve its exact wording and all other entries.",
    },
)
task = next(t for t in json.loads((root / "routing-tasks.json").read_text()) if t["id"] == "wheelhouse-1")
visible = modified[:16000].rsplit("\n", 1)[0]
parsed = parse_file(visible, meta["final_url"])
out = Path("evals/results/routing-order-iteration")
if out.exists():
    raise ValueError("Use a fresh output directory")
out.mkdir(parents=True)
client = OpenAI(timeout=60, max_retries=0)
rows = []
for repeat in range(1, 4):
    raw, metadata = model_route(
        client,
        os.environ.get("OPENAI_MODEL", "gpt-6-sol"),
        task["query"],
        {"file_url": meta["final_url"], "index": visible},
    )
    result = grade_routing(task, raw["urls"], parsed["links"] + parsed["bare_links"])
    row: dict[str, Any] = {
        "repeat": repeat,
        "response": raw,
        "result": result,
        "metadata": metadata,
        "variant_sha256": digest(modified.encode()),
    }
    rows.append(row)
    write_json(out / f"run-{repeat}.json", row)
write_json(
    out / "report.json",
    {"experiment": "Contact link ordering; same 16000-character budget and routing prompt", "results": rows},
)
print(sum(r["result"]["passed"] for r in rows), "/ 3 after moving contact route early")
