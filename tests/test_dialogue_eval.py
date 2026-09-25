from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from brief.contracts import GenerationInput
from brief.dialogue_eval import branches, grade
from brief.generation import build_request

CASES = json.loads(Path("evals/corpus/dialogue-cases.json").read_text())
CASE = CASES[0]
RAW: dict[str, Any] = {
    "guide": {"title": "Cove", "summary": None, "context": [], "sections": []},
    "explanation": "Rates conflict; preserve uncertainty until the owner confirms.",
    "questions": [
        {
            "topic": "current-rate",
            "question": "Which interest rate is current?",
            "rationale": "The two undated pages disagree, so this changes the rate we publish.",
            "evidenceIds": ["a", "b"],
            "options": ["Use 4.1%", "Do not quote a rate"],
            "recommendedOption": 1,
        }
    ],
}


def test_first_pass_quality_controls() -> None:
    assert grade(CASE, CASE["input"], RAW, "first")["passed"]
    missing = copy.deepcopy(RAW)
    missing["questions"] = []
    assert not grade(CASE, CASE["input"], missing, "first")["passed"]
    duplicate = copy.deepcopy(RAW)
    duplicate["questions"][0]["options"] = ["Same", "same"]
    assert not grade(CASE, CASE["input"], duplicate, "first")["passed"]
    no_reason = copy.deepcopy(RAW)
    no_reason["questions"][0]["rationale"] = "Because useful."
    assert not grade(CASE, CASE["input"], no_reason, "first")["passed"]


def test_actual_cards_drive_branches_without_mutating_first_pass() -> None:
    before = copy.deepcopy(RAW)
    rows = {stage: (context, expected) for stage, context, expected in branches(CASE, RAW)}
    assert rows["recommended"][0]["decisions"][-1]["statement"].endswith("Answer: Do not quote a rate")
    assert rows["alternative"][0]["decisions"][-1]["statement"].endswith("Answer: Use 4.1%")
    assert not rows["removed"][0]["decisions"][-1]["active"]
    assert "current-rate" not in rows["removed"][0]["dismissedTopics"]
    assert rows["more"][0]["mode"] == "questions"
    assert RAW == before
    request = build_request(GenerationInput.model_validate(rows["removed"][0]))
    assert "4.25" not in request["user"]
    assert "guide" not in json.loads(request["user"])


def test_no_recommendation_does_not_get_fabricated() -> None:
    raw = copy.deepcopy(RAW)
    raw["questions"][0]["recommendedOption"] = None
    assert "recommended" not in [r[0] for r in branches(CASE, raw)]
    assert branches(CASE, {**raw, "questions": []}) == []


def test_owner_fact_provenance_removal_and_custom_resource_selection() -> None:
    rows = {stage: (context, expected) for stage, context, expected in branches(CASE, RAW)}
    raw = copy.deepcopy(RAW)
    raw["questions"] = []
    raw["guide"]["context"] = [{"text": "Owner reports 4.25% annual interest.", "evidenceIds": ["answer"]}]
    context, expected = rows["custom"]
    assert grade(CASE, context, raw, "custom", expected)["passed"]
    raw["guide"]["context"][0]["evidenceIds"] = ["a"]
    assert not grade(CASE, context, raw, "custom", expected)["passed"]
    assert not grade(CASE, rows["removed"][0], raw, "removed", rows["removed"][1])["passed"]
    assert not grade(CASE, context, raw, "custom", {"include": ["a"]})["passed"]


def test_dismissal_and_question_only_do_not_mutate_document() -> None:
    rows = {stage: (context, expected) for stage, context, expected in branches(CASE, RAW)}
    assert not grade(CASE, rows["dismissed"][0], RAW, "dismissed")["passed"]
    assert not grade(CASE, rows["more"][0], RAW, "more")["passed"]
    empty: dict[str, Any] = {**RAW, "guide": None, "questions": []}
    assert grade(CASE, rows["more"][0], empty, "more")["passed"]


def test_reviewer_anchors_accept_real_structure_not_invented_quotes() -> None:
    from brief.dialogue_review import anchored_quote

    assert anchored_quote('"recommendedOption": 1', RAW)
    assert anchored_quote('"options": ["Use 4.1%", "Do not quote a rate"]', RAW)
    assert not anchored_quote('"recommendedOption": null', RAW)
    assert not anchored_quote("The current rate is 9.9%", RAW)
    assert not anchored_quote("", RAW)
