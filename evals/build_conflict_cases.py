"""Conflict regression states. All claims and owner replies are authored test data."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from brief.corpus import write_json

BASE: dict[str, Any] = {
    "siteUrl": "https://parcel.example/",
    "sources": [
        {
            "id": "home",
            "url": "https://parcel.example/",
            "title": "Parcel Shop",
            "description": "",
            "content": "Home delivery is free over €300. No date supplied.",
        },
        {
            "id": "policy",
            "url": "https://parcel.example/shipping",
            "title": "Shipping policy",
            "description": "",
            "content": "Home delivery is free over €600. No date supplied.",
        },
    ],
    "decisions": [],
    "dismissedTopics": [],
    "mode": "generate",
    "maxQuestions": 2,
}
cases = []


def decision(id: str, text: str, active: bool = True, kind: str = "fact") -> dict[str, Any]:
    return {"id": id, "kind": kind, "statement": text, "active": active}


def add(id: str, ctx: dict[str, Any], description: str, question: bool = False, **expected: Any) -> dict[str, Any]:
    case: dict[str, Any] = {
        "id": id,
        "kind": "authored-conflict",
        "category": "conflict-resolution",
        "split": "development",
        "description": description,
        "input": copy.deepcopy(ctx),
        "expected": {"include": [], "exclude": [], "forbidden": [], **expected},
    }
    if question:
        case["expected"].update(
            minQuestions=1, questionPattern="threshold|deliver|shipping|300|450|600|750|conflict|instruction|link"
        )
    else:
        case["expected"]["maxQuestions"] = 0
    cases.append(case)
    return case


add(
    "conflict-undated",
    BASE,
    "Equal-authority undated terms differ. Preserve uncertainty and ask; do not blend them.",
    True,
    documentPattern="conflict|differ|inconsisten|unconfirm|uncertain|300.*600",
    forbiddenDocument=["€450"],
)
c = copy.deepcopy(BASE)
c["sources"][0]["content"] = "Free pickup-point delivery in France with no minimum order."
c["sources"][1]["content"] = "Free home delivery in Germany over €600."
add(
    "conflict-different-scope",
    c,
    "Distinct country and delivery scopes are compatible; do not ask a fake conflict question.",
    documentPattern="France|Germany",
)
c = copy.deepcopy(BASE)
c["sources"][0]["content"] = (
    "Archived 2024 policy: free home delivery over €300. Superseded by the 2026 shipping policy."
)
c["sources"][1]["content"] = (
    "Effective September 1, 2026: free home delivery over €600. This policy replaces the 2024 terms."
)
add(
    "conflict-explicit-supersession",
    c,
    "Explicit effective date and supersession settle the conflict without owner input.",
    documentPattern="600",
)
c = copy.deepcopy(BASE)
c["decisions"] = [
    decision(
        "owner",
        "The current home-delivery threshold is €450. This owner correction supersedes the website until it is corrected.",
    )
]
add(
    "conflict-owner-resolution",
    c,
    "An explicit owner fact resolves site disagreement and needs owner provenance.",
    requiredClaim={"text": "450", "evidenceId": "owner"},
)
c["decisions"].append(decision("other", "The current home-delivery threshold is €750."))
add(
    "conflict-active-owner-answers",
    c,
    "Two active owner facts disagree. List order is not evidence of recency. Ask which remains authoritative.",
    True,
)
c2 = copy.deepcopy(c)
c2["decisions"].reverse()
add(
    "conflict-active-owner-answers-reversed",
    c2,
    "Permutation control: same conflict, opposite decision ordering; still ask.",
    True,
)
c["decisions"][0]["active"] = False
add(
    "conflict-owner-replacement",
    c,
    "Explicitly deactivate the old fact; use the replacement without asking again.",
    requiredClaim={"text": "750", "evidenceId": "other"},
    forbiddenDocument=["450"],
)
c["decisions"][1]["active"] = False
add(
    "conflict-remove-all-overrides",
    c,
    "Removing all owner resolutions restores the underlying source conflict.",
    True,
    forbiddenDocument=["450", "750"],
)
c = copy.deepcopy(BASE)
c["sources"][0]["content"] = "Free home delivery over €600."
c["sources"][1]["content"] = "Updated September 24, 2026: free home delivery over €600."
c["decisions"] = [
    decision(
        "owner", "Earlier confirmed owner correction: free home delivery over €450 until the website is corrected."
    )
]
add(
    "conflict-refresh-vs-owner",
    c,
    "Refreshed pages disagree with a conditional owner override. Ask whether its correction condition has been met; do not silently discard the owner.",
    True,
)
c["dismissedTopics"] = ["shipping threshold"]
add(
    "conflict-refresh-dismissed-topic",
    c,
    "Desired behavior: materially new evidence should reopen a conflict even if its topic was dismissed. Current topic-only suppression may fail.",
    True,
)
c = copy.deepcopy(BASE)
c["decisions"] = [
    decision(
        "unsure",
        "I cannot verify either amount. Omit numeric delivery thresholds and link the policy until I confirm.",
        kind="preference",
    )
]
add(
    "conflict-defer-resolution",
    c,
    "An explicit defer is actionable: omit the disputed claim, retain useful links, do not force a fact.",
    forbiddenDocument=["300", "600"],
)
c = copy.deepcopy(BASE)
c["dismissedTopics"] = ["shipping threshold"]
c["decisions"] = [
    decision(
        "omit",
        "Do not ask more about shipping. Do not assert either threshold as current; omit numeric amounts.",
        kind="preference",
    )
]
add(
    "conflict-dismiss-is-not-fact",
    c,
    "Dismissal is not confirmation. Respect omission and retain useful navigation.",
    forbiddenDocument=["300", "600"],
)
c = copy.deepcopy(BASE)
c["decisions"] = [
    decision("limit", "Include exactly one resource link.", kind="preference"),
    decision("both", "Include both homepage and shipping policy as separate resource links.", kind="preference"),
]
add(
    "conflict-incompatible-constraints",
    c,
    "Ask which incompatible active editorial constraint to relax rather than pretending both are satisfied.",
    True,
)
write_json(Path("evals/corpus/conflict-cases.json"), cases)
print(len(cases), "conflict cases")
