from __future__ import annotations

import inspect
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from brief.api import create_app
from brief.crawl.fetch import Response
from brief.crawl.runner import crawl
from brief.db import require_row
from brief.worker import run_once

if TYPE_CHECKING:
    from brief.crawl.runner import CrawlResult
    from brief.interfaces import URLPolicy
    from brief.store import Store


pytestmark = pytest.mark.integration


async def test_api_to_real_extraction_to_snapshot_and_changed_refresh(store: Store, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("BRIEF_CREATION_KEY", raising=False)
    body = (Path(__file__).parent / "fixtures" / "agency.html").read_bytes()

    class FixtureTransport:
        interval = 0.0

        async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
            verdict = allowed(url)
            assert await verdict if inspect.isawaitable(verdict) else verdict
            return (
                Response(url, 200, "text/html", body)
                if url == "https://example.com/"
                else Response(url, 404, "text/plain", b"")
            )

    async def crawler(url: str, previous: Sequence[str]) -> CrawlResult:
        return await crawl(url, previous, fetcher=FixtureTransport())

    with TestClient(create_app(store)) as client:
        created = client.post("/api/projects", json={"url": "https://example.com/"}).json()
        url = f"/api/projects/{created['project']['id']}"
        auth = {"Authorization": f"Bearer {created['management_token']}"}
        assert await run_once(store, crawler=crawler)
        first = client.get(url, headers=auth).json()
        assert first["jobs"][0]["status"] == "succeeded"
        assert "discovery workshop" in first["snapshot"]["sources"][0]["content"]
        assert first["snapshot"]["changes"]["added"] == ["https://example.com/"]
        first_id = first["snapshot"]["id"]
        body = body.replace(b"discovery workshop", b"paid discovery workshop")
        assert client.post(url + "/refresh", headers={**auth, "Idempotency-Key": "edit"}).status_code == 202
        assert await run_once(store, crawler=crawler)
        updated = client.get(url, headers=auth).json()
        assert updated["snapshot"]["changes"]["modified"] == ["https://example.com/"]
        assert updated["snapshot"]["id"] != first_id
        assert "paid discovery workshop" in updated["snapshot"]["sources"][0]["content"]
        previous = client.get(url + f"/snapshots/{first_id}", headers=auth).json()
        assert "paid discovery workshop" not in previous["sources"][0]["content"]
        other, other_token, _ = store.create_project("https://other.example.com/")
        assert (
            client.get(
                f"/api/projects/{other['id']}/snapshots/{first_id}", headers={"Authorization": f"Bearer {other_token}"}
            ).status_code
            == 404
        )
        assert created is not None
        assert (
            require_row(store.get_project(UUID(created["project"]["id"]), created["management_token"]))["revision"] == 2
        )
