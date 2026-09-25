"""Versioned clarification scenarios; real captures stay distinguishable from authored evidence."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from brief.corpus import write_json

authored = {c["id"]: c for c in json.loads(Path("evals/corpus/authored-generation-cases.json").read_text())}
cases = []


def add(
    id: str,
    base: dict[str, Any],
    pattern: str | None = None,
    kind: str = "authored",
    rubric: str = "",
    custom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = copy.deepcopy(base)
    context.update(mode="generate", maxQuestions=2)
    cases.append(
        {
            "id": id,
            "kind": kind,
            "input": context,
            "ambiguity_pattern": pattern,
            "rubric": rubric,
            "custom": custom,
            "expect_question": bool(pattern),
        }
    )
    return cases[-1]


def fact(text: str, pattern: str) -> dict[str, Any]:
    return {"kind": "fact", "statement": text, "document_pattern": pattern, "removed_forbidden": pattern}


add(
    "undated-interest-conflict",
    authored["source-date-unknown"]["input"],
    "rate|interest|4[.]1|3[.]8",
    rubric="Both undated rates have equal authority. Ask which is current or offer omission pending verification. Explain the conflict. Never recommend picking the higher rate as fact.",
    custom=fact(
        "I checked with the owner: the current annual interest rate is 4.25%. Use that rate and identify this as owner-provided.",
        r"4[.]25",
    ),
)
c = add(
    "shelter-priority",
    authored["charity-two-audiences"]["input"],
    "audience|priorit|help|donor|donat|bed",
    rubric="Only one resource is allowed. Recipient intake versus donor information is a consequential choice. Offer concrete alternatives and explain the default without claiming to know the owner intent.",
    custom={
        "kind": "preference",
        "statement": "Prioritize people seeking a bed. Include only the intake resource; no donation, impact, or staff-shop links.",
        "include": ["help"],
        "exclude": ["donate", "impact", "shop"],
    },
)
c["input"]["decisions"] = [
    {
        "id": "budget",
        "kind": "preference",
        "statement": "This guide must contain exactly one resource link. I have not chosen which audience to prioritize.",
        "active": True,
    }
]
# Actual conflicting homepage and policy captures discovered during the consumer pilot.
from brief.consumer_eval import PageStore

store = PageStore("evals/corpus/consumer-pages")
pages = [store.get(u) for u in ["https://we-in-style.com/", "https://we-in-style.com/policies/shipping-policy"]]
context: dict[str, Any] = {
    "siteUrl": "https://we-in-style.com/",
    "sources": [
        {"id": f"page{i}", "url": p["url"], "title": p["title"], "description": "", "content": p["content"]}
        for i, p in enumerate(pages)
    ],
    "decisions": [],
    "dismissedTopics": [],
}
add(
    "real-shipping-conflict",
    context,
    "shipping|delivery|300|600|threshold",
    kind="real-capture",
    rubric="Homepage and shipping policy disagree on free delivery thresholds. Cite both. Do not silently resolve the contradiction or recommend a new threshold as fact. Linking policy without quoting a number is a reasonable temporary suggestion.",
    custom=fact(
        "I own the store. The free home-delivery threshold is now €450. The website is awaiting correction. Use €450 and distinguish this owner update from the captured pages.",
        r"450",
    ),
)
context = copy.deepcopy(authored["local-service-scope"]["input"])
context["sources"][0]["content"] += " We do not serve San Francisco."
context["sources"][1]["content"] = "Service area: Oakland, Berkeley, and San Francisco. No effective date."
add(
    "service-area-conflict",
    context,
    "Francisco|area|coverage|geograph|serv",
    rubric="The overview lists Oakland/Berkeley while service-area page includes San Francisco. Ask whether SF is served, explain conflicting scope, suggest cautious wording rather than inventing broad coverage.",
    custom=fact(
        "Owner correction: service is now limited to Alameda only. Replace all previous city coverage statements.",
        "Alameda",
    ),
)
context = copy.deepcopy(authored["removed-direction-trajectory"]["input"])
context["decisions"] = [
    {
        "id": "budget",
        "kind": "preference",
        "statement": "Include exactly one resource link. The site does not establish whether this guide should serve API implementers or buyers.",
        "active": True,
    }
]
add(
    "developer-or-buyer",
    context,
    "audience|developer|buyer|API|pricing|plan|priorit",
    rubric="Choose between API implementation and buying/plans under one-link limit. Options should change the actual chosen link, with a grounded tentative recommendation.",
    custom={
        "kind": "preference",
        "statement": "This guide is for buyers only. Include the plans resource and exclude API documentation.",
        "include": ["plans"],
        "exclude": ["api"],
    },
)
for id in ["sparse-portfolio", "local-service-scope", "question-only-no-filler"]:
    c = add(
        "no-filler-" + id,
        authored[id]["input"],
        rubric="Evidence supports a useful default. Do not invent questions merely to use the budget, and do not repeat dismissed topics.",
    )
    if id == "question-only-no-filler":
        c["input"]["mode"] = "questions"
write_json(Path("evals/corpus/dialogue-cases.json"), cases)
print(len(cases), "dialogue cases")
