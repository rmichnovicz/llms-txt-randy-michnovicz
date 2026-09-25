from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from brief.contracts import GenerationInput, validate_result
from brief.evals import grade
from brief.generation import build_request, render_guide
from brief.refresh import Observation, RefreshState, StoredPage, content_hash, reconcile_pages, refresh_action

CASES = {c["id"]: c for c in json.loads(Path("evals/cases.json").read_text())}
CONTEXT = GenerationInput.model_validate(CASES["sensible-defaults"]["input"])


def good() -> dict[str, Any]:
    return {
        "guide": {
            "title": "Acme",
            "summary": {"text": "Document search API.", "evidenceIds": ["home"]},
            "context": [],
            "sections": [
                {
                    "title": "Resources",
                    "links": [{"sourceId": id, "label": id, "description": None} for id in ["api", "pricing"]],
                }
            ],
        },
        "explanation": "Useful product resources.",
        "questions": [],
    }


def test_removed_decisions_never_enter_request() -> None:
    request = build_request(GenerationInput.model_validate(CASES["removed-answer"]["input"]))
    assert "OLD_DECISION_MARKER" not in request["user"]
    assert json.loads(request["user"])["decisions"] == []


def test_active_fact_survives_context() -> None:
    request = build_request(GenerationInput.model_validate(CASES["user-fact"]["input"]))
    assert json.loads(request["user"])["decisions"][0]["id"] == "launch"


def test_unknown_source_and_inactive_evidence() -> None:
    result = good()
    result["guide"]["sections"][0]["links"][0]["sourceId"] = "invented"
    with pytest.raises(ValueError, match="Unknown source"):
        validate_result(result, CONTEXT)
    result = good()
    result["guide"]["summary"]["evidenceIds"] = ["old"]
    with pytest.raises(ValueError, match="inactive evidence"):
        validate_result(result, GenerationInput.model_validate(CASES["removed-answer"]["input"]))


def test_duplicate_links() -> None:
    result = good()
    result["guide"]["sections"][0]["links"] *= 2
    with pytest.raises(ValueError, match="Duplicate source"):
        validate_result(result, CONTEXT)


def test_dismissed_topic_and_invalid_option() -> None:
    result = good()
    result["questions"] = [
        {
            "topic": "audience",
            "question": "Audience?",
            "rationale": "Changes ordering.",
            "evidenceIds": ["home"],
            "options": ["Developers", "Buyers"],
            "recommendedOption": 2,
        }
    ]
    with pytest.raises(ValueError, match="answer does not exist"):
        validate_result(result, CONTEXT)
    result["questions"][0]["recommendedOption"] = 0
    with pytest.raises(ValueError, match="dismissed"):
        validate_result(result, CONTEXT.model_copy(update={"dismissed_topics": ["audience"]}))
    with pytest.raises(ValueError, match="budget"):
        validate_result(result, CONTEXT.model_copy(update={"max_questions": 0}))


def test_question_mode_does_not_mutate_document() -> None:
    context = CONTEXT.model_copy(update={"mode": "questions"})
    with pytest.raises(ValueError, match="must not mutate"):
        validate_result(good(), context)
    result = good()
    result["guide"] = None
    assert validate_result(result, context).guide is None


def test_render_shape_and_verified_markdown_url() -> None:
    guide = validate_result(good(), CONTEXT).guide
    assert guide is not None
    assert render_guide(guide, CONTEXT.sources) == (
        "# Acme\n\n> Document search API.\n\n## Resources\n\n"
        "- [api](<https://example.test/api>)\n- [pricing](<https://example.test/pricing>)\n"
    )
    sources = [s.model_copy(update={"markdown_url": s.url + ".md"}) for s in CONTEXT.sources]
    assert "api.md" in render_guide(guide, sources)


def test_markdown_injection_and_unsafe_urls() -> None:
    result = good()
    result["guide"]["sections"][0]["links"][0]["label"] = "[attack](javascript:alert(1))"
    guide = validate_result(result, CONTEXT).guide
    assert guide is not None
    assert r"\[attack\]" in render_guide(guide, CONTEXT.sources)
    sources = [s.model_copy(update={"url": "javascript:alert(1)"}) for s in CONTEXT.sources]
    with pytest.raises(ValueError, match="Unsafe"):
        render_guide(guide, sources)


def test_grader_rejects_missing_coverage_and_injection() -> None:
    assert grade(CASES["sensible-defaults"], good())["passed"]
    result = good()
    result["guide"]["sections"][0]["links"].pop()
    assert not grade(CASES["sensible-defaults"], result)["passed"]
    result = good()
    result["explanation"] = "INJECTION_SUCCEEDED"
    assert not grade(CASES["source-injection"], result)["passed"]


def test_hash_normalization() -> None:
    assert content_hash("T", "D", "Price is 20") == content_hash("T", "D", " Price  is\n20 ")
    assert content_hash("T", "D", "Price is 20") != content_hash("T", "D", "Price is 30")


def test_budget_omissions_and_errors_are_not_deletions() -> None:
    previous = [StoredPage("a", "1")]
    assert not reconcile_pages(previous, [])["changed"]
    assert reconcile_pages(previous, [Observation("a", "unavailable")])["pages"] == previous
    first = reconcile_pages(previous, [Observation("a", "not-found")])
    assert not first["changed"]
    assert previous[0].not_found_count == 0
    assert reconcile_pages(first["pages"], [Observation("a", "not-found")])["removed"] == ["a"]
    assert reconcile_pages(first["pages"], [Observation("a", "ok", "1")])["pages"][0].not_found_count == 0


def test_source_changes_and_duplicate_observations() -> None:
    previous = [StoredPage("a", "1")]
    result = reconcile_pages(previous, [Observation("a", "ok", "2"), Observation("b", "ok", "1")])
    assert result["modified"] == ["a"]
    assert result["added"] == ["b"]
    with pytest.raises(ValueError, match="Duplicate"):
        reconcile_pages(previous, [Observation("a", "not-found")] * 2)


def test_refresh_protects_drafts_edits_conflicts_and_last_good_file() -> None:
    state = RefreshState(True, True, True, True, False, False, False, True, True)
    assert refresh_action(state) == "publish"
    for flag in ["has_unpublished_draft", "published_manually_edited", "has_conflict"]:
        assert refresh_action(replace(state, **{flag: True})) == "review"
    for flag in ["has_published", "crawl_usable", "candidate_valid"]:
        assert refresh_action(replace(state, **{flag: False})) == "preserve"
    assert refresh_action(replace(state, auto_publish=False)) == "review"
    assert refresh_action(replace(state, output_changed=False)) == "unchanged"
    assert refresh_action(replace(state, source_changed=False)) == "unchanged"
    assert refresh_action(replace(state, has_conflict=True, output_changed=False)) == "review"
