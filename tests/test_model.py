from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIConnectionError, APIStatusError

from brief.contracts import GenerationInput
from brief.generation import build_request
from brief.model import ModelError, OpenAIGenerator


def context() -> GenerationInput:
    return GenerationInput(
        site_url="https://example.com/", sources=[], decisions=[], dismissed_topics=[], mode="generate", max_questions=3
    )


def raw() -> dict[str, Any]:
    return {
        "guide": {"title": "Example", "summary": None, "context": [], "sections": []},
        "explanation": "A minimal guide.",
        "questions": [],
    }


class FakeClient:
    def __init__(self, response: SimpleNamespace | None = None, error: Exception | None = None) -> None:
        self.responses = self
        self.request: dict[str, Any] | None = None
        self.error = error
        self.response = response or SimpleNamespace(
            status="completed",
            output=[],
            output_text=json.dumps(raw()),
            model="test-model",
            id="test-response",
            usage=None,
        )

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        if self.error:
            raise self.error
        return self.response


def test_structured_request_settings_and_usage_metadata() -> None:
    client = FakeClient()
    completion = OpenAIGenerator(client=client).generate(context())
    assert completion.raw == raw()
    assert client.request is not None
    assert client.request["store"] is False
    assert client.request["text"]["format"]["strict"] is True
    assert client.request["reasoning"] == {"effort": "medium"}
    assert client.request["max_output_tokens"] == 12000
    assert completion.metadata["attempts"] == 1
    assert completion.metadata["model"] == "test-model"


@pytest.mark.parametrize("status,retryable", [(400, False), (401, False), (429, True), (503, True)])
def test_error_messages_do_not_expose_provider_bodies_or_keys(status: int, retryable: bool) -> None:
    response = httpx.Response(status, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    error = APIStatusError("sensitive-error-body", response=response, body={"message": "sensitive-error-body"})
    with pytest.raises(ModelError) as caught:
        OpenAIGenerator(client=FakeClient(error=error)).generate(context())
    assert "sensitive" not in str(caught.value)
    assert caught.value.retryable == retryable


def test_quota_errors_are_not_retried() -> None:
    error = APIStatusError(
        "quota",
        response=httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com")),
        body={"code": "insufficient_quota"},
    )
    with pytest.raises(ModelError) as caught:
        OpenAIGenerator(client=FakeClient(error=error)).generate(context())
    assert not caught.value.retryable


def test_network_errors_are_retriable() -> None:
    error = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    with pytest.raises(ModelError) as caught:
        OpenAIGenerator(client=FakeClient(error=error)).generate(context())
    assert caught.value.retryable


@pytest.mark.parametrize(
    "change",
    [
        {"status": "incomplete"},
        {"output_text": "bad JSON"},
        {"output": [SimpleNamespace(type="message", content=[SimpleNamespace(type="refusal")])]},
    ],
)
def test_incomplete_invalid_and_refused_outputs_are_not_documents(change: dict[str, Any]) -> None:
    client = FakeClient()
    for key, value in change.items():
        setattr(client.response, key, value)
    with pytest.raises(ModelError):
        OpenAIGenerator(client=client).generate(context())


def test_source_validation_still_applies_to_schema_valid_outputs() -> None:
    response = raw()
    response["guide"]["summary"] = {"text": "Unsupported claim", "evidenceIds": ["invented"]}
    client = FakeClient()
    client.response.output_text = json.dumps(response)
    with pytest.raises(ModelError, match="source or decision"):
        OpenAIGenerator(client=client).generate(context())


def test_input_budget_prevents_api_call() -> None:
    client = FakeClient()
    request = build_request(context())
    request["user"] = "x" * 750001
    with pytest.raises(ModelError, match="budget"):
        OpenAIGenerator(client=client).complete(request)
    assert client.request is None


@pytest.mark.parametrize(
    "code", ["credit_balance_exhausted", "project_spend_limit_exceeded", "organization_usage_limit_exceeded"]
)
def test_billing_429_is_actionable_and_never_retried(code: str) -> None:
    error = APIStatusError(
        "secret-body",
        response=httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com")),
        body={"code": code, "type": "insufficient_quota"},
    )
    with pytest.raises(ModelError) as caught:
        OpenAIGenerator(client=FakeClient(error=error)).generate(context())
    assert not caught.value.retryable
    assert "billing" in str(caught.value)
    assert "secret" not in str(caught.value)
