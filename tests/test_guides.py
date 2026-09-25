from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

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


def test_consolidation_preserves_uncovered_pages_scope_hubs_and_distinct_fragments() -> None:
    from brief.guides import consolidate_links

    markdown = (
        "# Site\n\n## Details\n\n- [Detail](<https://example.com/help/detail>): Read it.\n\n"
        "## Other resources\n\n- [Help](<https://example.com/help/>): Start here.\n"
        "- [Uncovered](<https://example.com/help/unique>): Important.\n"
        "- [Pricing](<https://example.com/pricing>): Plans.\n"
        "- [Other host](<https://other.example.com/help/detail>): External.\n"
        "- [Specific section](<https://example.com/help/detail#advanced>): Advanced.\n"
    )
    children = [
        {
            "guide_path": "/help/",
            "markdown": (
                "# Help\n\n## Pages\n\n- [Detail](<detail>)\n- [Home](</help/>)\n"
                "- [Pricing](</pricing>)\n- [Other host](<https://other.example.com/help/detail>)\n"
            ),
        }
    ]
    updated = consolidate_links(markdown, "https://example.com/", children)
    assert "## Details" not in updated
    assert "- [Detail]" not in updated
    for label in ["Help", "Uncovered", "Pricing", "Other host", "Specific section"]:
        assert f"- [{label}]" in updated
    assert consolidate_links(updated, "https://example.com/", children) == updated
    assert consolidate_links(markdown, "https://example.com/", []) == markdown


def finish_all_links(store: Store, *, shortcut: str | None = None, owner_directed: bool = True) -> None:
    """Stand in for the model: one section per source, plus an optional parent entry point."""
    from brief.model import Completion

    job = require_row(store.claim())
    context = store.generation_context(job)
    guide: dict[str, Any] = {
        "title": "Site",
        "summary": None,
        "context": [],
        "sections": [
            {"title": s.title, "links": [{"source_id": s.id, "label": s.title, "description": None}]}
            for s in context.sources
        ],
    }
    if shortcut:
        chosen = next(s for s in context.sources if urlsplit(s.url).path == shortcut)
        guide["shortcuts"] = [
            {
                "source_id": chosen.id,
                "reason": "The owner asked the guide to lead with this task.",
                "decision_ids": [d.id for d in context.decisions if d.active] if owner_directed else [],
            }
        ]
    store.finish_generation(
        job,
        context,
        Completion(
            {"guide": guide, "questions": [], "explanation": "Include the captured resources."},
            {},
        ),
    )


@pytest.mark.integration
def test_ready_child_consolidates_parent_and_child_edits_restore_uncovered_links(store: Store) -> None:
    parent, token, _ = store.create_project("https://example.com/")
    sources = [source("https://example.com" + path) for path in ["/", "/help/", "/help/detail", "/help/unique"]]
    for i, item in enumerate(sources):
        item.id, item.title = f"source-{i}", f"Resource {i}"
    store.finish_crawl(require_row(store.claim()), result(*sources), enqueue_generation=True)
    finish_all_links(store)
    original = require_row(store.get_project(parent["id"], token))["draft"]
    child = create_guide(store, parent["id"], path="/help/", name="Help", purpose="Help readers")
    assert require_row(store.get_project(parent["id"], token))["draft"]["id"] == original["id"]
    store.finish_crawl(require_row(store.claim()), result(*sources[1:3]), enqueue_generation=True)
    finish_all_links(store)
    updated = require_row(store.get_project(parent["id"], token))
    text = updated["draft"]["markdown"]
    assert "/help/detail" not in text and "## Resource 2" not in text
    assert "/help/unique" in text and "/help/>" in text and "/help/llms.txt" in text
    with store.db.connect() as c:
        assert (
            require_row(c.execute("SELECT markdown FROM document_versions WHERE id=%s", (original["id"],)).fetchone())[
                "markdown"
            ]
            == original["markdown"]
        )
    store.enqueue_generation(parent["id"], "regenerate")
    finish_all_links(store)
    state = require_row(store.get_project(parent["id"], token))
    assert "/help/detail" not in state["proposal"]["markdown"]
    child_state = require_row(store.get_project(child["id"], token))
    child_version = child_state["draft_version_id"]
    editor.save_document(store, child["id"], child_state["revision"], "# Help\n\nNo detailed resources listed.\n")
    state = require_row(store.get_project(parent["id"], token))
    assert "/help/detail" in state["draft"]["markdown"]
    assert "/help/detail" in state["proposal"]["markdown"]
    child_state = require_row(store.get_project(child["id"], token))
    editor.use_version(store, child["id"], child_state["revision"], child_version)
    state = require_row(store.get_project(parent["id"], token))
    assert "/help/detail" not in state["draft"]["markdown"]
    custom = "# My guide\n\n## Keep this shortcut\n\n- [Detail](<https://example.com/help/detail>)\n"
    editor.save_document(store, parent["id"], state["revision"], custom)
    child_state = require_row(store.get_project(child["id"], token))
    editor.save_document(store, child["id"], child_state["revision"], "# Help\n\n- [Detail](<detail>)\n")
    assert require_row(store.get_project(parent["id"], token))["draft"]["markdown"].startswith(custom)


def test_owner_shortcut_is_retained_while_secondary_duplicates_delegate() -> None:
    from brief.guides import consolidate_links

    markdown = (
        "# Site\n\n## Start here\n\n- [Import forms](<https://example.com/help/import>): Bring existing forms.\n\n"
        "## More features\n\n- [Detail](<https://example.com/help/detail>): Secondary reference.\n"
    )
    children = [{"guide_path": "/help/", "markdown": "# Help\n\n- [Detail](<detail>)\n- [Import](<import>)\n"}]
    # Without a retention reason the strict rule delegates both.
    assert "/help/import" not in consolidate_links(markdown, "https://example.com/", children)
    kept = consolidate_links(markdown, "https://example.com/", children, {"https://example.com/help/import"})
    assert "- [Import forms]" in kept and "## Start here" in kept
    assert "- [Detail]" not in kept and "## More features" not in kept
    assert consolidate_links(kept, "https://example.com/", children, {"https://example.com/help/import"}) == kept


def guide_hops(guides: dict[str, str], start: str, target: str) -> int | None:
    """Guide files a reader must open before the destination becomes visible."""
    seen, frontier, hops = {start}, [start], 0
    while frontier:
        found = [link["url"] for page in frontier for link in parse_file(guides[page], page)["links"]]
        if target in found:
            return hops
        frontier = [url for url in found if url in guides and url not in seen]
        seen.update(frontier)
        hops += 1
    return None


def scoped_sources(*paths: str) -> list[Any]:
    sources = [source("https://example.com" + path) for path in paths]
    for i, item in enumerate(sources):
        item.id, item.title = f"source-{i}", f"Resource {i}"
    return sources


def build_root_with_owner_shortcut(store: Store) -> tuple[dict[str, Any], str, list[Any]]:
    """Root guide whose owner chose importing; /help/import is the priority entry point."""
    project, token, _ = store.create_project("https://example.com/")
    sources = scoped_sources("/", "/help/", "/help/import", "/help/detail")
    store.finish_crawl(require_row(store.claim()), result(*sources), enqueue_generation=True)
    finish_all_links(store)
    state = require_row(store.get_project(project["id"], token))
    saved = editor.save_decision(
        store, project["id"], state["revision"], statement="Lead with importing existing forms", kind="preference"
    )
    finish_all_links(store, shortcut="/help/import")
    project = require_row(store.get_project(project["id"], token))
    project["decision_id"] = saved["decision_id"]
    return project, token, sources


@pytest.mark.integration
def test_owner_shortcut_survives_child_creation_and_completion(store: Store) -> None:
    root, token, sources = build_root_with_owner_shortcut(store)
    before = root["draft"]["markdown"]
    assert "/help/import" in before and "/help/detail" in before
    child = create_guide(store, root["id"], path="/help/", name="Help", purpose="Help readers")
    # An unfinished child must not disturb the parent.
    assert require_row(store.get_project(root["id"], token))["draft"]["id"] == root["draft"]["id"]
    # The child orders its own section list differently; that must not move the root's priority.
    store.finish_crawl(require_row(store.claim()), result(*sources[1:][::-1]), enqueue_generation=True)
    finish_all_links(store)
    state = require_row(store.get_project(root["id"], token))
    text = state["draft"]["markdown"]
    assert "https://example.com/help/import" in text  # owner priority kept as a direct shortcut
    assert "/help/detail" not in text  # secondary duplicate delegated
    assert "## Resource 3" not in text  # emptied section removed
    assert "https://example.com/help/>" in text  # section landing page kept
    assert "https://example.com/help/llms.txt" in text  # navigation to the child guide
    child_text = require_row(store.get_project(child["id"], token))["draft"]["markdown"]
    assert child_text.index("/help/detail") < child_text.index("/help/import")

    # Acceptance 8: the reader still reaches import guidance directly; detail costs one hop.
    guides = {"https://example.com/llms.txt": text, "https://example.com/help/llms.txt": child_text}
    assert guide_hops(guides, "https://example.com/llms.txt", "https://example.com/help/import") == 0
    assert guide_hops(guides, "https://example.com/llms.txt", "https://example.com/help/detail") == 1
    assert covering_guide("https://example.com/help/detail", guides) == "https://example.com/help/llms.txt"
    before_guides = {"https://example.com/llms.txt": before}
    assert guide_hops(before_guides, "https://example.com/llms.txt", "https://example.com/help/import") == 0

    # A fresh root generation with the child already ready agrees with the reconciled draft.
    store.enqueue_generation(root["id"], "regenerate")
    finish_all_links(store, shortcut="/help/import")
    state = require_row(store.get_project(root["id"], token))
    assert "/help/import" in state["proposal"]["markdown"]
    assert "/help/detail" not in state["proposal"]["markdown"]
    with zipfile.ZipFile(io.BytesIO(bundle(store, root["site_id"]))) as archive:
        assert archive.read("llms.txt").decode() == state["draft"]["markdown"]

    # Repeated reconciliation is idempotent and adds no versions.
    versions = len(state["versions"])
    with store.db.connect() as c:
        from brief.guides import link_ready_child

        child_row = require_row(c.execute("SELECT * FROM projects WHERE id=%s", (child["id"],)).fetchone())
        link_ready_child(c, child_row)
        link_ready_child(c, child_row)
    assert len(require_row(store.get_project(root["id"], token))["versions"]) == versions


@pytest.mark.integration
def test_changed_direction_moves_the_shortcut_and_removal_releases_it(store: Store) -> None:
    root, token, sources = build_root_with_owner_shortcut(store)
    create_guide(store, root["id"], path="/help/", name="Help", purpose="Help readers")
    store.finish_crawl(require_row(store.claim()), result(*sources[1:]), enqueue_generation=True)
    finish_all_links(store)
    state = require_row(store.get_project(root["id"], token))
    assert "/help/import" in state["draft"]["markdown"]

    editor.save_decision(
        store,
        root["id"],
        state["revision"],
        decision_id=root["decision_id"],
        statement="Lead with the detailed reference instead",
        kind="preference",
    )
    finish_all_links(store, shortcut="/help/detail")
    text = require_row(store.get_project(root["id"], token))["draft"]["markdown"]
    assert "/help/detail" in text and "/help/import" not in text

    # Deactivating the direction releases the shortcut even before any regeneration runs.
    with store.db.connect() as c:
        from brief.guides import link_ready_child

        c.execute("UPDATE decisions SET active=false WHERE project_id=%s", (root["id"],))
        child_row = require_row(
            c.execute("SELECT * FROM projects WHERE site_id=%s AND guide_path='/help/'", (root["site_id"],)).fetchone()
        )
        link_ready_child(c, child_row)
    released = require_row(store.get_project(root["id"], token))["draft"]["markdown"]
    assert "/help/detail" not in released and "/help/import" not in released
    assert "https://example.com/help/>" in released and "/help/llms.txt" in released


@pytest.mark.integration
def test_reconciliation_reaches_intermediate_ancestors(store: Store) -> None:
    project, token, _ = store.create_project("https://example.com/")
    sources = scoped_sources("/", "/docs/", "/docs/api/", "/docs/api/auth")
    store.finish_crawl(require_row(store.claim()), result(*sources), enqueue_generation=True)
    finish_all_links(store)
    middle = create_guide(store, project["id"], path="/docs/", name="Docs", purpose="Help developers")
    store.finish_crawl(require_row(store.claim()), result(*sources[1:]), enqueue_generation=True)
    finish_all_links(store)
    leaf = create_guide(store, project["id"], path="/docs/api/", name="API", purpose="Help API readers")
    store.finish_crawl(require_row(store.claim()), result(*sources[2:]), enqueue_generation=True)
    finish_all_links(store)
    middle_text = require_row(store.get_project(middle["id"], token))["draft"]["markdown"]
    assert "/docs/api/auth" not in middle_text
    assert "https://example.com/docs/api/llms.txt" in middle_text
    with zipfile.ZipFile(io.BytesIO(bundle(store, project["site_id"]))) as archive:
        assert archive.read("docs/llms.txt").decode() == middle_text
    assert leaf["id"] != middle["id"]


@pytest.mark.integration
def test_version_history_names_automatic_relinks(store: Store) -> None:
    """An app-managed relink is neither a manual edit nor a fresh generation."""
    project, token, _ = store.create_project("https://example.com/")
    sources = scoped_sources("/", "/help/", "/help/detail")
    store.finish_crawl(require_row(store.claim()), result(*sources), enqueue_generation=True)
    finish_all_links(store)
    create_guide(store, project["id"], path="/help/", name="Help", purpose="Help readers")
    store.finish_crawl(require_row(store.claim()), result(*sources[1:]), enqueue_generation=True)
    finish_all_links(store)
    state = require_row(store.get_project(project["id"], token))
    editor.save_document(
        store, project["id"], state["revision"], "# Mine\n\n- [D](<https://example.com/help/detail>)\n"
    )
    child = require_row(store.get_project(project["id"], token))["guides"][1]
    child_state = require_row(store.get_project(child["id"], token))
    editor.save_document(store, child["id"], child_state["revision"], "# Help\n\n- [Other](<other>)\n")
    origins = [
        (v["origin"], v["manually_edited"]) for v in require_row(store.get_project(project["id"], token))["versions"]
    ]
    # Newest first: relink of the manual edit, the manual edit, relink of the draft, the draft.
    assert origins == [
        ("related-guide-link", True),
        ("manual", True),
        ("related-guide-link", False),
        (None, False),
    ]
