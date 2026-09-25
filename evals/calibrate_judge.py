"""Construct six positive/negative pairs to check whether semantic review detects known defects."""

import copy
import json
from pathlib import Path

from brief.corpus import write_json

root = Path("evals/results/judge-calibration-inputs")
if root.exists():
    raise ValueError("Use a fresh calibration input directory")
root.mkdir(parents=True)
pairs = [
    ("local-service-scope", "development", "grounding", "24/7 emergency electricians serving San Francisco."),
    (
        "store-returns",
        "development",
        "grounding",
        "All shoes, including final-sale and used items, have free returns for 90 days.",
    ),
    ("preference-is-not-fact", "development", "grounding", "Linden Advisory is ISO 27001 certified."),
    ("manufacturer-variants", "holdout", "grounding", "Sensor A supports -40 to 120 C and is rated IP67."),
    ("restaurant-allergens", "holdout", "grounding", "Elm Kitchen guarantees every meal is nut-free."),
    (
        "sparse-portfolio",
        "holdout",
        "grounding",
        "Ari Chen is an award-winning illustrator whose clients include Apple and Nike.",
    ),
]
labels = []
for i, (case, split, dimension, claim) in enumerate(pairs):
    original = json.loads(Path(f"evals/results/corpus-v2-{split}/{case}--r1.json").read_text())
    for bad in [False, True]:
        row = copy.deepcopy(original)
        # IDs are never passed to the judge. It sees only evidence and candidate.
        row["id"] = f"calibration-{i + 1}-{int(bad)}--r1"
        if bad:
            context = json.loads(row["request"]["user"])
            row["response"]["guide"]["summary"] = {"text": claim, "evidenceIds": [context["sources"][0]["id"]]}
        write_json(root / f"{row['id']}.json", row)
        labels.append(
            {
                "id": row["id"],
                "has_known_defect": bad,
                "dimension": dimension,
                "defect": "Unsupported or contradicted summary with an otherwise valid evidence ID" if bad else None,
            }
        )
write_json(Path("evals/corpus/judge-calibration-labels.json"), labels)
