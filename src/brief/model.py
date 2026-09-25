"""OpenAI Responses adapter; keeps SDK errors and credentials out of app logs."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, APIStatusError, OpenAI
from openai.types.shared import ReasoningEffort
from pydantic import BaseModel

from brief.contracts import GenerationInput, GenerationResult, validate_result
from brief.generation import build_request
from brief.interfaces import ModelClient


class ModelError(ValueError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class Completion:
    raw: dict[str, Any]
    metadata: dict[str, Any]


class OpenAIGenerator:
    def __init__(
        self,
        *,
        client: ModelClient | None = None,
        model: str | None = None,
        reasoning: ReasoningEffort | None = "medium",
        max_output_tokens: int = 12000,
    ) -> None:
        self.client: ModelClient = client if client is not None else OpenAI(timeout=75, max_retries=0)
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-6-sol")
        self.reasoning = reasoning
        self.max_output_tokens = max_output_tokens

    def complete(self, request: dict[str, Any], *, result_type: type[BaseModel] = GenerationResult) -> Completion:
        # Source caps bound the request before sending it; no automatic multi-call repair.
        if len(request["user"]) > 750_000:
            raise ModelError("Generation input exceeds character budget")
        start = time.monotonic()
        try:
            response = self.client.responses.create(
                model=self.model,
                **({"reasoning": {"effort": self.reasoning}} if self.reasoning is not None else {}),
                input=[{"role": "system", "content": request["system"]}, {"role": "user", "content": request["user"]}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "llms_guide",
                        "strict": True,
                        "schema": request["outputSchema"],
                    }
                },
                max_output_tokens=self.max_output_tokens,
                store=False,
            )
        except APIStatusError as error:
            # Never include error bodies: authentication errors can echo portions of a key.
            billing = {
                "insufficient_quota",
                "credit_balance_exhausted",
                "project_spend_limit_exceeded",
                "organization_spend_limit_exceeded",
                "organization_usage_limit_exceeded",
            }
            if error.status_code == 429 and (error.code in billing or error.type == "insufficient_quota"):
                message = (
                    "OpenAI API credits are exhausted. Add credits in API billing, then retry."
                    if error.code == "credit_balance_exhausted"
                    else "OpenAI API quota or spend limit reached. Check API billing and limits before retrying."
                )
                raise ModelError(message, retryable=False) from None
            retryable = error.status_code >= 500 or error.status_code == 429
            raise ModelError(f"OpenAI request failed (HTTP {error.status_code})", retryable=retryable) from None
        except APIConnectionError:
            raise ModelError("OpenAI connection failed or timed out", retryable=True) from None
        if response.status != "completed":
            raise ModelError("Model response incomplete; no document saved")
        if any(part.type == "refusal" for item in response.output if item.type == "message" for part in item.content):
            raise ModelError("Model declined the request; no document saved")
        try:
            raw = json.loads(response.output_text)
            result_type.model_validate(raw)
        except (ValueError, TypeError):
            raise ModelError("Model returned an invalid document structure") from None
        return Completion(
            raw=raw,
            metadata={
                "provider": "openai",
                "model": response.model,
                "reasoning": self.reasoning,
                "prompt_version": request["promptVersion"],
                "response_id": response.id,
                "duration_ms": round((time.monotonic() - start) * 1000),
                "usage": response.usage.model_dump() if response.usage else None,
                "max_output_tokens": self.max_output_tokens,
                "attempts": 1,
            },
        )

    def generate(self, context: GenerationInput) -> Completion:
        completion = self.complete(build_request(context))
        try:
            validate_result(completion.raw, context)
        except ValueError:
            raise ModelError("Model output failed source or decision validation") from None
        return completion
