from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pytest import MonkeyPatch

from brief import consumer_eval as ev

URL = "https://example.com/policy"
TEXT = "Custom samples are reimbursable when ordering at least 500 units."
TASK: dict[str, Any] = {
    "id": "sample",
    "question": "When reimbursable?",
    "facts": [
        {"id": "quantity", "answer_patterns": ["500"], "quote_patterns": ["at least 500 units"], "evidence_urls": [URL]}
    ],
}


def answer(url: str = URL, quote: str = TEXT) -> dict[str, Any]:
    return {
        "action": "answer",
        "url": None,
        "answer": "At least 500 units.",
        "citations": [{"url": url, "quote": quote}],
    }


@pytest.mark.parametrize(
    "quote,valid",
    [
        (TEXT, True),
        ("Custom samples are reimbursable … at least 500 units.", True),
        ("Custom samples are reimbursable when ordering at least 100 units.", False),
        ("at least 500 units. ... Custom samples are reimbursable", False),
        ("500", False),
    ],
)
def test_quote_provenance(quote: str, valid: bool) -> None:
    assert ev.quote_matches(quote, TEXT) is valid


def test_answer_requires_observed_support() -> None:
    observed = {URL: {"url": URL, "content": TEXT}}
    assert ev.grade_answer(TASK, answer(), observed)["grounded_success"]
    assert not ev.grade_answer(TASK, answer(), {})["grounded_success"]
    assert not ev.grade_answer(TASK, answer(quote="At least 100 units."), observed)["grounded_success"]
    response = answer()
    response["citations"] = []
    grade = ev.grade_answer(TASK, response, observed)
    assert grade["answer_correct"] and not grade["grounded_success"]
    response["answer"] = "100 units"
    assert not ev.grade_answer(TASK, response, observed)["answer_correct"]


def test_redirect_alias_and_abstention() -> None:
    alias = "https://example.com/old-policy"
    assert ev.grade_answer(TASK, answer(url=alias), {alias: {"url": URL, "content": TEXT}})["grounded_success"]
    task: dict[str, Any] = {"facts": [], "expect_abstain": True, "forbidden_patterns": [r"\$\d"]}
    response: dict[str, Any] = {"action": "abstain", "answer": "The exact future rate is unknown.", "citations": []}
    assert ev.grade_answer(task, response, {})["grounded_success"]
    response["answer"] = "Maybe $50"
    assert not ev.grade_answer(task, response, {})["grounded_success"]


class Client:
    def __init__(self, actions: list[dict[str, Any]]) -> None:
        self.actions = iter(actions)
        self.prompts: list[dict[str, Any]] = []
        self.responses = self

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.prompts.append(kwargs)
        return SimpleNamespace(status="completed", output_text=json.dumps(next(self.actions)), usage=None)


def test_unknown_links_never_fetched_and_gold_not_exposed(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    entry: dict[str, Any] = {"url": "https://example.com/llms.txt", "content": TEXT, "links": []}
    monkeypatch.setattr(ev, "initial_page", lambda *a: entry)
    store = SimpleNamespace(get=lambda u: pytest.fail("Unobserved URL fetched"))
    client = Client([{"action": "open", "url": URL}, answer()])
    row = ev.run_trial(TASK, "generated", 1, store, client, "fake", tmp_path, max_opens=1)
    assert row["opens"] == 1
    assert not row["grade"]["grounded_success"]
    assert "evidence_urls" not in json.dumps(client.prompts)
    assert "URL was not observed" in json.dumps(row["observations"])


def test_budget_and_guide_are_not_answer_evidence(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ev, "initial_page", lambda *a: {"url": URL, "content": TEXT, "links": []})
    store = SimpleNamespace(get=lambda u: pytest.fail("Unexpected fetch"))
    row = ev.run_trial(TASK, "generated", 1, store, Client([answer()]), "fake", tmp_path)
    assert not row["grade"]["grounded_success"]
    row = ev.run_trial(TASK, "homepage", 1, store, Client([answer()]), "fake", tmp_path)
    assert row["grade"]["grounded_success"]
    row = ev.run_trial(
        TASK, "homepage", 2, store, Client([{"action": "open", "url": URL}]), "fake", tmp_path, max_opens=0
    )
    assert row["errors"] and row["opens"] == 0


def test_offline_cache_miss(tmp_path: Path) -> None:
    assert ev.PageStore(tmp_path).get(URL)["cache_miss"]
