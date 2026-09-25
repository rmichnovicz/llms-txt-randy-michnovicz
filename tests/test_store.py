from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from brief.api import create_app
from brief.contracts import Source
from brief.crawl.runner import CrawlResult
from brief.db import require_row
from brief.refresh import Observation, content_hash
from brief.store import LeaseLost
from brief.worker import run_once

if TYPE_CHECKING:
    from brief.db import Database
    from brief.store import Store


pytestmark = pytest.mark.integration


def source(
    url: str = "https://example.com/", content: str = "Useful content about the company's product and services."
) -> Source:
    return Source(
        id="root" if url.endswith("/") else "other",
        url=url,
        title="Example",
        description="Example site",
        content=content,
    )


def result(*sources: Source) -> CrawlResult:
    return CrawlResult(
        sources=list(sources),
        observations=[Observation(s.url, "ok", content_hash(s.title, s.description, s.content)) for s in sources],
        attempted=len(sources),
        discovered=len(sources),
    )


def expire(database: Database, job: dict[str, Any]) -> None:
    with database.connect() as connection:
        connection.execute("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s", (job["id"],))


def test_migration_is_idempotent(database: Database) -> None:
    database.migrate()
    with database.connect() as connection:
        assert require_row(connection.execute("SELECT count(*) AS n FROM schema_migrations").fetchone())["n"] == 11


def test_creation_and_enqueue_are_one_transaction(store: Store, monkeypatch: MonkeyPatch) -> None:
    def fail(*args: Any) -> None:
        raise RuntimeError("injected enqueue failure")

    monkeypatch.setattr(store, "_enqueue", fail)
    with pytest.raises(RuntimeError):
        store.create_project("https://example.com/")
    with store.db.connect() as connection:
        assert require_row(connection.execute("SELECT count(*) AS n FROM projects").fetchone())["n"] == 0


def test_concurrent_workers_claim_distinct_jobs(store: Store) -> None:
    store.create_project("https://example.com/")
    store.create_project("https://example.org/")
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda _: store.claim(), range(2)))
    assert len({require_row(job)["id"] for job in jobs}) == 2
    assert store.claim() is None


def test_only_one_worker_claims_single_job(store: Store) -> None:
    store.create_project("https://example.com/")
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: store.claim(), range(4)))
    assert sum(job is not None for job in claims) == 1


def test_expired_lease_is_reclaimed_and_old_worker_cannot_commit(store: Store) -> None:
    store.create_project("https://example.com/")
    first = store.claim()
    assert first is not None
    expire(store.db, first)
    assert not store.renew(first)
    second = store.claim()
    assert second is not None
    assert first["id"] == second["id"] and first["lease_token"] != second["lease_token"]
    assert second["attempt"] == 2
    with pytest.raises(LeaseLost):
        store.finish_crawl(first, result(source()))
    store.finish_crawl(second, result(source()))
    assert store.claim() is None
    with pytest.raises(LeaseLost):
        store.finish_crawl(second, result(source()))


def test_exhausted_crashes_release_active_project_slot(store: Store) -> None:
    project, _, _ = store.create_project("https://example.com/")
    for _ in range(3):
        job = store.claim()
        assert job is not None
        expire(store.db, job)
    assert store.claim() is None
    new = store.enqueue_refresh(project["id"], "after-crash")
    assert new["status"] == "pending"


def test_stale_revision_does_not_replace_new_state(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")
    job = store.claim()
    with store.db.connect() as connection:
        connection.execute("UPDATE projects SET revision = revision + 1 WHERE id = %s", (project["id"],))
    assert job is not None
    assert store.finish_crawl(job, result(source()))["status"] == "superseded"
    assert require_row(store.get_project(project["id"], token))["latest_snapshot_id"] is None


def test_refresh_idempotency_and_retry_backoff(store: Store) -> None:
    project, token, initial = store.create_project("https://example.com/")
    assert store.enqueue_refresh(project["id"], "check")["id"] == initial["id"]
    job = store.claim()
    assert job is not None
    store.fail(job, "temporary failure")
    assert store.claim() is None
    with store.db.connect() as connection:
        connection.execute("UPDATE jobs SET available_at = now() WHERE id = %s", (job["id"],))
    retry = store.claim()
    assert retry is not None
    assert retry["attempt"] == 2
    store.finish_crawl(retry, result(source()))
    refresh = store.enqueue_refresh(project["id"], "check")
    store.finish_crawl(require_row(store.claim()), result(source()))
    assert store.enqueue_refresh(project["id"], "check")["id"] == refresh["id"]
    assert require_row(store.get_project(project["id"], token))["revision"] == 2


def test_failed_crawl_preserves_last_good_snapshot_and_records_failure(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")
    store.finish_crawl(require_row(store.claim()), result(source()))
    original = require_row(store.get_project(project["id"], token))["latest_snapshot_id"]
    store.enqueue_refresh(project["id"], "failure")
    summary = store.finish_crawl(require_row(store.claim()), CrawlResult(warnings=[{"reason": "timeout"}]))
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["latest_snapshot_id"] == original
    assert state["last_check_status"] == "failed"
    assert state["jobs"][0]["status"] == "pending"
    assert summary["status"] == "failed"
    assert state["jobs"][0]["result"]["warnings"] == [{"reason": "timeout"}]


def test_two_explicit_missing_checks_remove_but_omissions_and_errors_do_not(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")
    missing = source("https://example.com/old")
    store.finish_crawl(require_row(store.claim()), result(source(), missing))
    outcomes: list[Literal["unavailable", "not-found"] | None] = [None, "unavailable", "not-found", "not-found"]
    for index, outcome in enumerate(outcomes):
        store.enqueue_refresh(project["id"], f"check-{index}")
        crawl_result = result(source())
        if outcome:
            crawl_result.observations.append(Observation(missing.url, outcome))
        summary = store.finish_crawl(require_row(store.claim()), crawl_result)
        snapshot = require_row(store.get_project(project["id"], token))["snapshot"]
        if index < 3:
            assert len(snapshot["sources"]) == 2
            assert summary["changes"]["removed"] == []
        else:
            assert len(snapshot["sources"]) == 1
            assert summary["changes"]["removed"] == [missing.url]


def test_schedule_is_opt_in_and_idempotent(store: Store) -> None:
    project, _, _ = store.create_project("https://example.com/")
    store.finish_crawl(require_row(store.claim()), result(source()))
    with store.db.connect() as connection:
        connection.execute("UPDATE projects SET next_check_at = now() - interval '1 day'")
    assert store.schedule_due() == 0
    store.set_monitoring(project["id"], True)
    assert store.schedule_due() == 1
    assert store.schedule_due() == 0
    assert require_row(store.claim())["kind"] == "refresh"


async def test_worker_saves_snapshot_without_model_provider(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")

    async def crawler(url: str, previous: Sequence[str]) -> CrawlResult:
        assert url == project["site_url"] and previous == []
        return result(source())

    assert await run_once(store, crawler=crawler)
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["snapshot"]["sources"][0]["content"] == source().content
    assert state["jobs"][0]["status"] == "succeeded"
    assert not await run_once(store, crawler=crawler)


async def test_worker_exception_is_retriable(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")

    async def broken(*args: Any) -> CrawlResult:
        raise RuntimeError("simulated crash")

    await run_once(store, crawler=broken)
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["jobs"][0]["status"] == "pending"
    assert state["jobs"][0]["error"] == "Worker error (RuntimeError)"


def test_api_authorization_validation_and_project_isolation(store: Store, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("BRIEF_CREATION_KEY", "private-demo")
    client = TestClient(create_app(store))
    assert client.post("/api/projects", json={"url": "https://example.com/"}).status_code == 403
    headers = {"X-Creation-Key": "private-demo"}
    assert client.post("/api/projects", json={"url": "http://127.0.0.1/"}, headers=headers).status_code == 422
    created = client.post("/api/projects", json={"url": "https://example.com/"}, headers=headers)
    assert created.status_code == 202
    body = created.json()
    path = f"/api/projects/{body['project']['id']}"
    assert "management_token_hash" not in created.text
    assert client.get(path).status_code in {401, 403}
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 404
    headers = {"Authorization": f"Bearer {body['management_token']}"}
    assert client.get(path, headers=headers).status_code == 200
    assert client.post(path + "/refresh", headers=headers).status_code == 422
    headers["Idempotency-Key"] = "one"
    assert client.post(path + "/refresh", headers=headers).json()["job_id"] == body["job_id"]
    assert client.patch(path + "/monitoring", headers=headers, json={"enabled": True}).status_code == 200
    other, _, _ = store.create_project("https://other.example.com/")
    assert client.get(f"/api/projects/{other['id']}", headers=headers).status_code == 404
    assert client.get(path + f"/snapshots/{uuid4()}", headers=headers).status_code == 404
    assert client.get("/health").status_code == 200
