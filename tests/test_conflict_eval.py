from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from brief.benchmark import grade_generation
from brief.contracts import GenerationInput
from brief.generation import build_request

CASES = {c["id"]: c for c in json.loads(Path("evals/corpus/conflict-cases.json").read_text())}


def candidate(
    question: bool = False, text: str = "Delivery terms are unconfirmed.", evidence: list[str] | None = None
) -> dict[str, Any]:
    return {
        "guide": {
            "title": "Parcel Shop",
            "summary": None,
            "context": [{"text": text, "evidenceIds": evidence or ["home", "policy"]}],
            "sections": [
                {
                    "title": "Shipping",
                    "links": [{"sourceId": "policy", "label": "Shipping policy", "description": None}],
                }
            ],
        },
        "explanation": "Resolve delivery terms using the available evidence.",
        "questions": [
            {
                "topic": "terms",
                "question": "Which shipping threshold is authoritative?",
                "rationale": "The sources conflict, so confirmation changes the published delivery claim.",
                "evidenceIds": ["home", "policy"],
                "options": ["Confirm a threshold", "Omit the disputed claim"],
                "recommendedOption": 1,
            }
        ]
        if question
        else [],
    }


def test_conflict_cases_validate_and_do_not_leak_gold() -> None:
    for case in CASES.values():
        request = build_request(GenerationInput.model_validate(case["input"]))
        assert "expected" not in json.loads(request["user"])
        assert case["description"] not in request["user"]


def test_conflict_requires_question_but_scoped_terms_do_not() -> None:
    unresolved = CASES["conflict-undated"]
    assert grade_generation(unresolved, candidate(True))["passed"]
    assert not grade_generation(unresolved, candidate())["passed"]
    scoped = CASES["conflict-different-scope"]
    output = candidate(text="Pickup in France and home delivery in Germany have different terms.")
    assert grade_generation(scoped, output)["passed"]
    output["questions"] = candidate(True)["questions"]
    assert not grade_generation(scoped, output)["passed"]


def test_owner_fact_requires_provenance_and_removed_fact_is_excluded() -> None:
    case = CASES["conflict-owner-resolution"]
    assert grade_generation(case, candidate(text="Owner-confirmed threshold: €450.", evidence=["owner"]))["passed"]
    assert not grade_generation(case, candidate(text="Owner-confirmed threshold: €450."))["passed"]
    removed = CASES["conflict-remove-all-overrides"]
    request = json.loads(build_request(GenerationInput.model_validate(removed["input"]))["user"])
    assert request["decisions"] == []
    assert not grade_generation(removed, candidate(True, text="The current threshold is €750."))["passed"]


def test_defer_is_not_confirmation_and_order_does_not_change_gold() -> None:
    case = CASES["conflict-defer-resolution"]
    assert grade_generation(case, candidate())["passed"]
    assert not grade_generation(case, candidate(text="Delivery is free over €600."))["passed"]
    normal = copy.deepcopy(CASES["conflict-active-owner-answers"])
    reversed_case = CASES["conflict-active-owner-answers-reversed"]
    assert normal["input"]["decisions"] == list(reversed(reversed_case["input"]["decisions"]))
    assert normal["expected"] == reversed_case["expected"]
