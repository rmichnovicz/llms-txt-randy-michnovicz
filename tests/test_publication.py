from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from test_editor import setup_project

from brief import editor, publication
from brief.api import create_app
from brief.crawl.fetch import FetchError, Response
from brief.db import require_row

if TYPE_CHECKING:
    from brief.interfaces import URLPolicy
    from brief.store import Store


class Fetcher:
    interval = 0.0

    def __init__(self, responses: dict[str, tuple[int, str, bytes]]) -> None:
        self.responses = responses
        self.visited: list[str] = []

    async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
        assert allowed(url)
        assert not allowed("http://127.0.0.1/llms.txt")
        assert not allowed("https://other.example.com/llms.txt")
        self.visited.append(url)
        status, mime, body = self.responses.get(url, (404, "text/plain", b"Not found"))
        return Response(url, status, mime, body)


def test_candidates_walk_every_ancestor() -> None:
    assert publication.candidates("https://example.com/docs/api/v2/") == [
        "https://example.com/docs/api/v2/llms.txt",
        "https://example.com/docs/api/llms.txt",
        "https://example.com/docs/llms.txt",
        "https://example.com/llms.txt",
    ]


@pytest.mark.parametrize(
    "mime,body",
    [
        ("text/html", b"# Error"),
        ("text/plain", b"<!doctype html><h1>Oops</h1>"),
        ("application/json", b'{"error": "missing"}'),
        ("text/plain", b"# \n"),
        ("text/plain", b"# Fake\n<html>error</html>"),
        ("text/plain", b"# Title\n\xff"),
    ],
)
def test_rejects_false_guide_responses(mime: str, body: bytes) -> None:
    with pytest.raises(FetchError):
        publication.markdown(Response("https://example.com/llms.txt", 200, mime, body))


async def test_discovery_retains_provenance_and_rejects_soft_404() -> None:
    fetcher = Fetcher(
        {
            "https://example.com/docs/llms.txt": (200, "text/html", b"<h1>Not found</h1>"),
            "https://example.com/llms.txt": (200, "text/plain", b"# Existing\n\n> Summary\n"),
        }
    )
    report = await publication.inspect("https://example.com/docs/", fetcher=fetcher)
    assert report["complete"]
    assert len(report["guides"]) == 1
    assert report["guides"][0]["url"] == "https://example.com/llms.txt"
    assert len(report["guides"][0]["sha256"]) == 64
    assert report["checked_at"]
    assert len(report["checks"]) == 2


async def test_verification_only_checks_exact_install_path() -> None:
    fetcher = Fetcher({"https://example.com/llms.txt": (200, "text/plain", b"# Root")})
    report = await publication.inspect("https://example.com/docs/", exact=True, fetcher=fetcher)
    assert not report["guides"]
    assert "https://example.com/llms.txt" not in fetcher.visited


async def test_discovery_respects_robots_and_records_failure() -> None:
    class RobotsFetcher(Fetcher):
        async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
            if not allowed(url):
                raise FetchError("Disallowed by robots.txt")
            return await super().get(url, allowed=allowed)

    fetcher = RobotsFetcher(
        {"https://example.com/robots.txt": (200, "text/plain", b"User-agent: *\nDisallow: /llms.txt")}
    )
    report = await publication.inspect("https://example.com/", fetcher=fetcher)
    assert not report["guides"]
    assert report["checks"][0]["status"] == "Disallowed by robots.txt"
    report = await publication.inspect(
        "https://example.com/",
        fetcher=Fetcher(
            {
                "https://example.com/robots.txt": (503, "text/plain", b"Unavailable"),
            }
        ),
    )
    assert not report["complete"] and report["error"]


@pytest.mark.integration
def test_publication_is_explicit_frozen_private_and_revocable(store: Store) -> None:
    project, token = setup_project(store)
    client = TestClient(create_app(store))
    path = f"/api/projects/{project['id']}"
    public = f"/api/published/{project['publication_id']}/llms.txt"
    auth = {"Authorization": f"Bearer {token}"}
    body: dict[str, Any] = {"revision": project["revision"], "version_id": str(project["draft"]["id"])}
    assert client.get(public).status_code == 404
    assert client.post(path + "/publication", json=body).status_code == 401
    assert (
        client.post(path + "/publication", headers=auth, json={**body, "version_id": str(uuid4())}).status_code == 409
    )
    assert client.post(path + "/publication", headers=auth, json=body).status_code == 200
    response = client.get(public)
    assert response.text == project["draft"]["markdown"]
    assert response.headers["content-type"].startswith("text/plain")
    assert token not in response.text
    assert client.get(public + "?download=true").headers["content-disposition"] == 'attachment; filename="llms.txt"'
    state = store.get_project(project["id"], token)
    assert state is not None
    editor.save_document(store, project["id"], state["revision"], "# Private edit\n\nNot published yet.\n")
    assert client.get(public).text == response.text
    assert client.post(path + "/publication", headers=auth, json=body).status_code == 409
    state = store.get_project(project["id"], token)
    assert state is not None
    assert (
        client.post(
            path + "/publication",
            headers=auth,
            json={
                "revision": state["revision"],
                "version_id": str(state["draft"]["id"]),
            },
        ).status_code
        == 200
    )
    assert "Private edit" in client.get(public).text
    state = store.get_project(project["id"], token)
    assert state is not None
    assert (
        client.post(
            path + "/publication", headers=auth, json={"revision": state["revision"], "version_id": None}
        ).status_code
        == 200
    )
    assert client.get(public).status_code == 404


@pytest.mark.integration
async def test_saved_check_and_installation_verification(store: Store, monkeypatch: MonkeyPatch) -> None:
    project, token = setup_project(store)
    client = TestClient(create_app(store))
    path = f"/api/projects/{project['id']}"
    auth = {"Authorization": f"Bearer {token}"}

    async def inspect(url: str, *, exact: bool = False) -> dict[str, Any]:
        assert url == project["site_url"]
        return {
            "complete": True,
            "checked_at": "2026-09-25T00:00:00Z",
            "checks": [],
            "guides": [
                {"url": url + "llms.txt", "markdown": project["draft"]["markdown"], "sha256": "fixture"},
            ],
        }

    monkeypatch.setattr(publication, "inspect", inspect)
    assert client.post(path + "/publication/verify", headers=auth).status_code == 409
    assert client.post(path + "/existing-guide", headers=auth).status_code == 200
    assert require_row(store.get_project(project["id"], token))["existing_guide_check"]["complete"]
    publication.publish(store, project["id"], project["revision"], project["draft"]["id"])
    assert client.post(path + "/publication/verify", headers=auth).json()["matches"]


@pytest.mark.integration
def test_publication_blocks_pending_work_and_unreviewed_answers(store: Store) -> None:
    project, token = setup_project(store)
    editor.save_decision(store, project["id"], project["revision"], statement="New direction", kind="preference")
    state = store.get_project(project["id"], token)
    with pytest.raises(editor.EditConflict, match="current update"):
        assert state is not None
        publication.publish(store, project["id"], state["revision"], state["draft"]["id"])
    store.fail(require_row(store.claim()), "Failed", retryable=False)
    with pytest.raises(editor.EditConflict, match="update the draft"):
        assert state is not None
        publication.publish(store, project["id"], state["revision"], state["draft"]["id"])
