"""Explain observed source changes against the saved document's evidence."""

from __future__ import annotations

from difflib import unified_diff
from typing import Any


def text(source: dict[str, Any]) -> str:
    return "\n".join(source.get(k, "") for k in ("title", "description", "content"))


def build(project: dict[str, Any]) -> list[dict[str, Any]]:
    draft = project.get("draft")
    snapshot = project.get("snapshot")
    if not draft or not snapshot:
        return []
    before = {s["id"]: s for s in draft["generation_input"].get("sources", [])}
    after = {s["id"]: s for s in snapshot["sources"]}
    sections = draft.get("structured_result", {}).get("guide") or {}
    items = []
    for sid in sorted(before.keys() | after.keys()):
        old, new = before.get(sid), after.get(sid)
        if old and new and text(old) == text(new):
            continue
        source = new or old
        assert source is not None
        affected = [
            s["title"]
            for s in sections.get("sections", [])
            if any(l.get("source_id", l.get("sourceId")) == sid for l in s["links"])
        ]
        decisions = [
            d["id"]
            for d in project["decisions"]
            if d["active"] and d["needs_review"] and any(s["id"] == sid for s in d["evidence_basis"])
        ]
        items.append(
            {
                "id": sid,
                "url": source["url"],
                "title": source["title"],
                "kind": "added" if not old else "removed" if not new else "modified",
                "before": old,
                "after": new,
                "sections": affected,
                "decision_ids": decisions,
                "diff": "\n".join(
                    unified_diff(
                        text(old).splitlines() if old else [],
                        text(new).splitlines() if new else [],
                        fromfile="Saved draft evidence",
                        tofile="Latest evidence",
                        lineterm="",
                    )
                ),
            }
        )
    return items
