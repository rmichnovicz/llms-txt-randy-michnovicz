from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from test_editor import finish, setup_project
from test_store import result, source

from brief import editor
from brief.api import create_app
from brief.corpus import parse_file
from brief.db import require_row
from brief.guides import bundle, covering_guide, create_guide, normalize_scope

if TYPE_CHECKING:
    from brief.store import Store


@pytest.mark.parametrize(
    "site,branch,page",
    [
        ("https://svelte.dev", "/docs/svelte/", "/docs/svelte/$state"),
        ("https://svelte.dev", "/docs/kit/", "/docs/kit/routing"),
        ("https://developers.cloudflare.com", "/workers/", "/workers/runtime-apis/fetch/"),
        ("https://developers.cloudflare.com", "/d1/", "/d1/get-started/"),
    ],
)
def test_frozen_parent_child_navigation_and_scope(site: str, branch: str, page: str) -> None:
    root = Path("evals/corpus/hierarchies")
    records = json.loads((root / "manifest.json").read_text())
    files = {}
    for record in records:
        body = (root / record["file"]).read_bytes()
        assert hashlib.sha256(body).hexdigest() == record["sha256"]
        files[record["url"]] = body.decode()
    parent = site + "/llms.txt"
    child = site + branch + "llms.txt"
    parsed = parse_file(files[parent], parent)
    assert child in [link["url"] for link in parsed["links"]]
    assert covering_guide(site + page, files) == child
    assert len(files[child].split()) > 100
    # Removing a child falls back to the applicable parent, never another sibling.
    assert covering_guide(site + page, [u for u in files if u != child]) == parent


def test_scope_boundaries_and_no_implicit_parent_instruction_merge() -> None:
    guides = [
        "https://example.com/llms.txt",
        "https://example.com/docs/llms.txt",
        "https://example.com/docs/api/llms.txt",
    ]
    assert covering_guide("https://example.com/docs/api/auth", guides) == guides[2]
    assert covering_guide("https://example.com/docs-other", guides) == guides[0]
    assert covering_guide("https://other.example.com/docs/api", guides) is None
    contents = {guides[0]: "Parent: use dollars", guides[2]: "API: use credits"}
    selected = covering_guide("https://example.com/docs/api/auth", guides)
    assert selected is not None
    assert contents[selected] == "API: use credits"  # Selection, not instruction inheritance.


@pytest.mark.parametrize("path", ["//evil.com/", "/../private/", "/%2e%2e/private/", "/docs?x=1", "/docs\\evil"])
def test_invalid_guide_scopes(path: str) -> None:
    with pytest.raises(editor.EditConflict):
        normalize_scope(path)


@pytest.mark.integration
def test_site_cookie_works_for_children_but_not_other_sites(store: Store) -> None:
    parent, token = setup_project(store)
    child = create_guide(store, parent["id"], path="/docs/", name="Docs", purpose="Help developers")
    other, _, _ = store.create_project("https://other.example.com/")
    with TestClient(create_app(store), base_url="https://testserver") as client:
        assert client.post(f"/api/projects/{parent['id']}/session", json={"token": token}).status_code == 200
        state = client.get(f"/api/projects/{child['id']}")
        assert state.status_code == 200
        assert state.json()["site_id"] == str(parent["site_id"])
        assert client.get(f"/api/projects/{other['id']}").status_code == 401
        assert client.get(f"/api/projects/{child['id']}/access-token").json()["token"] == token
        site_url = f"/api/projects/{parent['site_id']}/document"
        assert client.get(site_url).json()["id"] == str(parent["id"])
        selected = client.get(site_url, params={"doc": "/docs"})
        assert selected.status_code == 200
        assert selected.json()["id"] == str(child["id"])
        assert selected.json()["site_id"] == str(parent["site_id"])
        assert client.get(site_url, params={"doc": "/missing/"}).status_code == 404
        assert client.get(site_url, params={"doc": "/../docs/"}).status_code == 409
        assert client.get(f"/api/projects/{other['site_id']}/document").status_code == 401
        assert (
            client.get(
                f"/api/projects/{other['site_id']}/document", headers={"Authorization": f"Bearer {token}"}
            ).status_code
            == 404
        )


@pytest.mark.integration
def test_child_decisions_are_independent_and_bundle_preserves_paths(store: Store) -> None:
    parent, token = setup_project(store)
    child = create_guide(store, parent["id"], path="/docs/", name="Docs", purpose="Help developers")
    store.finish_crawl(require_row(store.claim()), result(source("https://example.com/docs/")), enqueue_generation=True)
    context = finish(store)
    assert context.decisions[0].id == "guide_purpose"
    state = store.get_project(child["id"], token)
    assert state is not None
    editor.save_decision(store, child["id"], state["revision"], statement="Use Python examples", kind="preference")
    finish(store)
    assert require_row(store.get_project(parent["id"], token))["decisions"] == []
    parent_version = require_row(store.get_project(parent["id"], token))["draft_version_id"]
    store.enqueue_refresh(child["id"], "child-change")
    store.finish_crawl(
        require_row(store.claim()),
        result(source("https://example.com/docs/", "New documentation content with changed behavior.")),
        enqueue_generation=True,
    )
    finish(store)
    assert require_row(store.get_project(parent["id"], token))["draft_version_id"] == parent_version
    with zipfile.ZipFile(io.BytesIO(bundle(store, parent["site_id"]))) as archive:
        assert set(archive.namelist()) == {"llms.txt", "docs/llms.txt"}
        assert b"docs/llms.txt" in archive.read("llms.txt")
    with pytest.raises(editor.EditConflict):
        create_guide(store, parent["id"], path="/docs", name="Duplicate", purpose="Duplicate")


@pytest.mark.integration
def test_upgrade_preserves_existing_draft_and_scope(store: Store) -> None:
    parent, token = setup_project(store)
    draft = parent["draft_version_id"]
    # Reconstruct the previous schema around real snapshot/document references.
    with store.db.connect() as c:
        c.execute("DROP TABLE page_cache")
        c.execute(
            "ALTER TABLE projects DROP COLUMN site_id, DROP COLUMN guide_path, DROP COLUMN guide_name, DROP COLUMN guide_purpose"
        )
        c.execute("DROP TABLE sites")
        c.execute("DELETE FROM schema_migrations WHERE name='006_sites_cache.sql'")
        c.execute("UPDATE projects SET site_url='https://example.com/docs' WHERE id=%s", (parent["id"],))
    store.db.migrate()
    restored = store.get_project(parent["id"], token)
    assert restored is not None
    assert restored["guide_path"] == "/docs/"
    assert restored["draft_version_id"] == draft
    assert restored["site_id"] == parent["id"]


@pytest.mark.integration
def test_automatic_guides_wait_for_root_are_idempotent_and_link_only_when_ready(store: Store) -> None:

    from brief.guides import cancel_automatic
    from brief.progress import read_progress

    parent, token, _ = store.create_project("https://example.com/")
    sources = [source()]
    for i in range(3):
        s = source(f"https://example.com/docs/page-{i}")
        s.id = f"docs-{i}"
        sources.append(s)
    store.finish_crawl(require_row(store.claim()), result(*sources), enqueue_generation=True)
    assert len(require_row(store.get_project(parent["id"], token))["guides"]) == 1
    finish(store)
    root = store.get_project(parent["id"], token)
    assert root is not None
    children = [g for g in root["guides"] if g["guide_path"] != "/"]
    assert len(children) == 1 and children[0]["auto_reason"]
    assert "docs/llms.txt" not in root["draft"]["markdown"]
    progress = read_progress(store, parent["id"])
    crawl = store.claim()
    assert crawl is not None
    assert crawl["project_id"] == children[0]["id"]
    assert read_progress(store, parent["id"]) != progress
    cancel_automatic(store, children[0]["id"])
    from brief.store import LeaseLost

    with pytest.raises(LeaseLost):
        store.finish_crawl(crawl, result(*sources[1:]), enqueue_generation=True)
    store.enqueue_generation(parent["id"], "repeat")
    finish(store)
    assert len(require_row(store.get_project(parent["id"], token))["guides"]) == 2
    assert (
        children[0]["guide_path"].lstrip("/") + "llms.txt"
        not in zipfile.ZipFile(io.BytesIO(bundle(store, parent["site_id"]))).namelist()
    )


@pytest.mark.integration
def test_ready_child_adds_immutable_root_version(store: Store) -> None:
    parent, token = setup_project(store)
    old = parent["draft"]
    create_guide(store, parent["id"], path="/help/", name="Help", purpose="Help customers")
    store.finish_crawl(require_row(store.claim()), result(source("https://example.com/help/")), enqueue_generation=True)
    finish(store)
    updated = store.get_project(parent["id"], token)
    assert old is not None
    assert updated is not None
    assert updated["draft"]["id"] != old["id"]
    assert old is not None
    assert updated["draft"]["markdown"].startswith(old["markdown"])
    assert "https://example.com/help/llms.txt" in updated["draft"]["markdown"]
    with store.db.connect() as c:
        assert old is not None
        assert (
            require_row(c.execute("SELECT markdown FROM document_versions WHERE id=%s", (old["id"],)).fetchone())[
                "markdown"
            ]
            == old["markdown"]
        )
    assert len(updated["guides"]) == 2  # no recursive auto-creation
