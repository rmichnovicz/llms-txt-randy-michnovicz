"""Exact validated generation reuse, isolated to one private guide workspace."""

from __future__ import annotations

import hashlib
import json
import os
import zlib
from typing import TYPE_CHECKING, Any

from brief.contracts import validate_result
from brief.generation import build_request
from brief.model import Completion, OpenAIGenerator

if TYPE_CHECKING:
    from brief.contracts import GenerationInput
    from brief.interfaces import Generator
    from brief.store import Store


def generate(store: Store, job: dict[str, Any], generator: Generator, context: GenerationInput) -> Completion:
    if not isinstance(generator, OpenAIGenerator) or os.environ.get("BRIEF_MODEL_CACHE", "true").lower() == "false":
        return generator.generate(context)
    request = build_request(context)
    identity: dict[str, Any] = {
        "version": 1,
        "request": request,
        "model": generator.model,
        "reasoning": generator.reasoning,
        "max_output_tokens": generator.max_output_tokens,
        "endpoint": str(getattr(generator.client, "base_url", "openai")),
    }
    key = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with store.db.connect() as c:
        row = c.execute(
            "SELECT payload,created_at FROM model_cache WHERE project_id=%s AND request_hash=%s AND created_at > now()-interval '7 days'",
            (job["project_id"], key),
        ).fetchone()
    if row:
        try:
            saved = json.loads(zlib.decompress(bytes(row["payload"])))
            validate_result(saved["raw"], context)
            return Completion(
                saved["raw"],
                {
                    "provider": "openai",
                    "model": generator.model,
                    "cache": {"status": "hit", "created_at": row["created_at"].isoformat(), "request_hash": key},
                    "attempts": 0,
                    "duration_ms": 0,
                    "usage": None,
                    "original_metadata": saved["metadata"],
                },
            )
        except (ValueError, TypeError, KeyError, zlib.error):
            pass  # Invalid cached outputs never become documents.
    completion = generator.generate(context)
    validate_result(completion.raw, context)
    payload = zlib.compress(json.dumps({"raw": completion.raw, "metadata": completion.metadata}).encode())
    with store.db.connect() as c:
        c.execute(
            """INSERT INTO model_cache(project_id,request_hash,payload) VALUES (%s,%s,%s)
            ON CONFLICT(project_id,request_hash) DO UPDATE SET payload=excluded.payload,created_at=now()""",
            (job["project_id"], key, payload),
        )
        c.execute(
            """DELETE FROM model_cache WHERE project_id=%s AND (created_at < now()-interval '7 days'
            OR request_hash NOT IN (SELECT request_hash FROM model_cache WHERE project_id=%s ORDER BY created_at DESC LIMIT 100))""",
            (job["project_id"], job["project_id"]),
        )
    return Completion(completion.raw, {**completion.metadata, "cache": {"status": "miss", "request_hash": key}})
