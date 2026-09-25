from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from test_editor import setup_project

from brief import editor, guide_tests
from brief.api import create_app
from brief.db import require_row
from brief.model import Completion, ModelError

if TYPE_CHECKING:
    from brief.store import Store


URL = "https://example.com/docs"
SOURCE: dict[str, Any] = {
    "id": "docs",
    "url": URL,
    "title": "API",
    "description": "API use",
    "content": "Authenticate with an API key. Recurring payments are not supported.",
}
QUESTION: dict[str, Any] = {
    "question": "How do I authenticate?",
    "expected_url": URL,
    "reference_quote": "Authenticate with an API key.",
}
ENTRY = guide_tests.guide_page(f"# Example\n\n## Docs\n- [API]({URL}): Authentication", "https://example.com/llms.txt")


def action(
    kind: str, *, url: str | None = None, answer: str = "", citations: Sequence[dict[str, str]] = ()
) -> dict[str, Any]:
    return {"action": kind, "url": url, "answer": answer, "citations": list(citations)}


class Reader:
    def __init__(self, *outputs: dict[str, Any]) -> None:
        self.outputs = iter(outputs)
        self.requests: list[dict[str, Any]] = []

    def complete(self, request: dict[str, Any], **kwargs: Any) -> Completion:
        self.requests.append(json.loads(request["user"]))
        return Completion(next(self.outputs), {"model": "fixture-reader"})


def test_reader_only_receives_opened_pages_and_checks_quote_provenance() -> None:
    reader = Reader(
        action("open", url=URL),
        action("answer", answer="Use an API key.", citations=[{"url": URL, "quote": "Authenticate with an API key."}]),
    )
    result = guide_tests.trial(reader, QUESTION, ENTRY, [SOURCE], [])
    assert result["outcome"] == "evidence_matched"
    assert "Recurring payments" not in json.dumps(reader.requests[0])
    assert "Recurring payments" in json.dumps(reader.requests[1])
    assert "expected_url" not in json.dumps(reader.requests)


@pytest.mark.parametrize(
    "url,quote", [(URL, "Invented fact from nowhere"), ("https://other.com/", "Authenticate with an API key.")]
)
def test_invented_or_unread_citations_fail(url: str, quote: str) -> None:
    reader = Reader(action("answer", answer="Use a key", citations=[{"url": url, "quote": quote}]))
    result = guide_tests.trial(reader, QUESTION, ENTRY, [SOURCE], [])
    assert result["outcome"] == "needs_review"
    assert "lacks valid quotes" in result["reason"]


def test_unknown_links_and_missing_frozen_pages_are_explicit() -> None:
    reader = Reader(
        action("open", url="https://unlisted.example.com/private"),
        action("open", url=URL),
        action("abstain", answer="The source is unavailable."),
    )
    result = guide_tests.trial(reader, QUESTION, ENTRY, [], [])
    assert "not present" in result["trace"][0]["result"]
    assert "not available" in result["trace"][1]["result"]
    assert result["outcome"] == "abstained"


def test_layered_guide_links_are_followed_without_revealing_other_sources() -> None:
    child = "https://example.com/docs/llms.txt"
    entry = guide_tests.guide_page(f"# Root\n- [Docs]({child})", "https://example.com/llms.txt")
    reader = Reader(
        action("open", url=child),
        action("open", url=URL),
        action("answer", answer="API key", citations=[{"url": URL, "quote": QUESTION["reference_quote"]}]),
    )
    result = guide_tests.trial(reader, QUESTION, entry, [SOURCE], [{"url": child, "content": ENTRY["content"]}])
    assert result["expected_reached"]
    assert result["trace"][0]["result"] == "Opened saved guide"


def test_browsing_budget_and_non_http_links() -> None:
    entry = guide_tests.guide_page(
        f"# Site\n[Email](mailto:a@example.com)\n[Docs]({URL})", "https://example.com/llms.txt"
    )
    assert entry["links"] == [URL]
    reader = Reader(*[action("open", url=URL) for _ in range(4)])
    result = guide_tests.trial(reader, QUESTION, entry, [SOURCE], [])
    assert "three-page" in result["reason"]
    assert len(reader.requests) == 4


def test_suggestions_are_derived_from_evidence_and_invalid_quotes_are_rejected() -> None:
    writer = Reader({"questions": [QUESTION]})
    questions, _ = guide_tests.suggest(writer, [SOURCE])
    assert questions == [QUESTION]
    assert set(writer.requests[0]) == {"evidence"}
    with pytest.raises(ModelError, match="evidence validation"):
        guide_tests.suggest(
            Reader({"questions": [{**QUESTION, "reference_quote": "No such quote in the page"}]}), [SOURCE]
        )


@pytest.mark.integration
async def test_run_is_immutable_idempotent_and_reuses_question_set(store: Store, monkeypatch: MonkeyPatch) -> None:
    parent, token = setup_project(store)
    args: dict[str, Any] = {
        "version_id": parent["draft_version_id"],
        "questions": ["What does this company do?"],
        "request_key": "one",
    }
    first = guide_tests.enqueue(store, parent["id"], **args)
    assert guide_tests.enqueue(store, parent["id"], **args) == first
    job = store.claim()

    async def progress(data: dict[str, Any]) -> None:
        assert job is not None
        store.report_progress(job, data)

    assert job is not None
    await guide_tests.run(
        store, job, None, progress, reader=Reader(action("abstain", answer="I cannot establish this."))
    )
    state = store.get_project(parent["id"], token)
    assert state is not None
    saved = state["test_runs"][0]
    assert saved["report"]["results"][0]["outcome"] == "abstained"
    assert state["draft_version_id"] == parent["draft_version_id"]
    editor.save_document(store, parent["id"], state["revision"], "# New version\n\nDifferent text.")
    state = store.get_project(parent["id"], token)
    monkeypatch.setenv("BRIEF_READER_MODEL", "different-model")
    assert saved is not None
    assert state is not None
    guide_tests.enqueue(
        store, parent["id"], version_id=state["draft_version_id"], suite_id=saved["suite_id"], request_key="two"
    )
    after = require_row(store.get_project(parent["id"], token))["test_runs"]
    assert after[0]["questions"] == saved["questions"]
    assert after[0]["reader_model"] == saved["reader_model"]
    assert after[0]["evidence_snapshot_id"] == saved["evidence_snapshot_id"]
    assert after[0]["version_id"] != saved["version_id"]
    assert after[1]["report"] == saved["report"]


@pytest.mark.integration
def test_api_auth_ownership_and_validation(store: Store) -> None:
    project, token = setup_project(store)
    other, _other_token = setup_project(store)
    client = TestClient(create_app(store))
    endpoint = f"/api/projects/{project['id']}/tests"
    body = {"version_id": str(project["draft_version_id"])}
    assert client.post(endpoint, json=body).status_code == 401
    headers: dict[str, Any] = {"Authorization": f"Bearer {token}", "Idempotency-Key": "one"}
    assert (
        client.post(endpoint, json={"version_id": str(other["draft_version_id"])}, headers=headers).status_code == 409
    )
    assert client.post(endpoint, json={**body, "questions": ["  "]}, headers=headers).status_code == 422
    assert client.post(endpoint, json={**body, "suite_id": str(uuid4())}, headers=headers).status_code == 409
    assert client.post(endpoint, json=body, headers=headers).status_code == 202
    assert client.post(endpoint, json=body, headers={**headers, "Idempotency-Key": "two"}).status_code == 409
