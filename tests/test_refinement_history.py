from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from test_editor import setup_project
from test_generation_jobs import Generator

from brief import editor
from brief.api import create_app
from brief.db import require_row

if TYPE_CHECKING:
    from brief.store import Store

pytestmark = pytest.mark.integration


def complete(store: Store, title: str) -> None:
    job = require_row(store.claim())
    context = store.generation_context(job)
    completion = Generator().generate(context)
    completion.raw["guide"]["title"] = title
    store.finish_generation(job, context, completion)


def test_refinement_logs_directions_and_keeps_baseline_after_restore(store: Store) -> None:
    project, token = setup_project(store)
    pid = project["id"]
    initial = project["draft"]
    assert "refinement" not in initial
    saved = editor.save_decision(store, pid, project["revision"], statement="For developers", kind="preference")
    complete(store, "Developer guide")
    state = require_row(store.get_project(pid, token))
    refined = state["draft"]
    log = refined["refinement"]
    assert log["before_version_id"] == initial["id"]
    assert log["before_markdown"] == initial["markdown"]
    assert "-# Example" in log["diff"] and "+# Developer guide" in log["diff"]
    assert log["directions"] == [{"kind": "added", "before": None, "after": "For developers"}]
    assert state["versions"][0]["refined_from_version_id"] == initial["id"]

    editor.use_version(store, pid, state["revision"], initial["id"])
    state = require_row(store.get_project(pid, token))
    editor.save_decision(
        store, pid, state["revision"], decision_id=saved["decision_id"], statement="For buyers", kind="preference"
    )
    complete(store, "Buyer guide")
    state = require_row(store.get_project(pid, token))
    # Creation order would choose the developer guide. The actual replaced draft was the original.
    assert state["draft"]["refinement"]["before_version_id"] == initial["id"]
    assert "-# Developer guide" not in state["draft"]["refinement"]["diff"]

    client = TestClient(create_app(store))
    response = client.get(f"/api/projects/{pid}/versions/{refined['id']}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["refinement"]["before_markdown"] == initial["markdown"]
    assert response.json()["refinement"]["directions"] == log["directions"]
    other, other_token = setup_project(store)
    assert (
        client.get(
            f"/api/projects/{other['id']}/versions/{refined['id']}", headers={"Authorization": f"Bearer {other_token}"}
        ).status_code
        == 404
    )


def test_updated_and_removed_directions_and_no_wording_change(store: Store) -> None:
    project, token = setup_project(store)
    pid = project["id"]
    saved = editor.save_decision(store, pid, project["revision"], statement="For developers", kind="preference")
    complete(store, "Example")
    state = require_row(store.get_project(pid, token))
    assert state["draft"]["refinement"]["diff"] == ""
    editor.save_decision(
        store, pid, state["revision"], decision_id=saved["decision_id"], statement="For buyers", kind="preference"
    )
    complete(store, "Example")
    state = require_row(store.get_project(pid, token))
    assert state["draft"]["refinement"]["directions"] == [
        {"kind": "updated", "before": "For developers", "after": "For buyers"}
    ]
    editor.save_decision(
        store,
        pid,
        state["revision"],
        decision_id=saved["decision_id"],
        statement="For buyers",
        kind="preference",
        active=False,
    )
    complete(store, "Example")
    state = require_row(store.get_project(pid, token))
    assert state["draft"]["refinement"]["directions"] == [{"kind": "removed", "before": "For buyers", "after": None}]


def test_refinement_baseline_includes_manual_wording(store: Store) -> None:
    project, token = setup_project(store)
    pid = project["id"]
    manual = editor.save_document(store, pid, project["revision"], "# Handwritten\n\nMy exact wording.\n")
    state = require_row(store.get_project(pid, token))
    assert "refinement" not in state["draft"]
    editor.save_decision(store, pid, state["revision"], statement="Shorten the guide", kind="preference")
    complete(store, "Example")
    log = require_row(store.get_project(pid, token))["draft"]["refinement"]
    assert log["before_version_id"] == manual["version_id"]
    assert "-My exact wording." in log["diff"]
