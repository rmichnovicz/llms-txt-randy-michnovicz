"""Compare refinements with the draft they actually replaced, including after restores."""

from __future__ import annotations

from difflib import unified_diff
from typing import Any

from psycopg import Connection


def attach(connection: Connection[dict[str, Any]], version: dict[str, Any] | None) -> None:
    if not version or not version.get("refined_from_version_id"):
        return
    before = connection.execute(
        "SELECT id, markdown, generation_input FROM document_versions WHERE id=%s AND project_id=%s",
        (version["refined_from_version_id"], version["project_id"]),
    ).fetchone()
    if not before:
        return
    old = {d["id"]: d for d in before["generation_input"].get("decisions", []) if d.get("active", True)}
    new = {d["id"]: d for d in version["generation_input"].get("decisions", []) if d.get("active", True)}
    directions = []
    for key in dict.fromkeys([*old, *new]):
        previous, current = old.get(key), new.get(key)
        if (
            previous
            and current
            and (previous["statement"], previous["kind"]) == (current["statement"], current["kind"])
        ):
            continue
        directions.append(
            {
                "kind": "added" if not previous else "removed" if not current else "updated",
                "before": previous["statement"] if previous else None,
                "after": current["statement"] if current else None,
            }
        )
    version["refinement"] = {
        "before_version_id": before["id"],
        "before_markdown": before["markdown"],
        "directions": directions,
        "diff": "\n".join(
            unified_diff(
                before["markdown"].splitlines(),
                version["markdown"].splitlines(),
                fromfile="Before refinement",
                tofile="After refinement",
                lineterm="",
            )
        ),
    }
