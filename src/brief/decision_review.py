"""Source-level review of saved answers; a change is not proof of contradiction."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from brief.refresh import content_hash


def source_hash(source: dict[str, Any]) -> str:
    return content_hash(source["title"], source["description"], source["content"])


def mark_changed_decisions(
    connection: Connection[dict[str, Any]], project_id: UUID, sources: list[dict[str, Any]]
) -> None:
    current = {s["id"]: s for s in sources}
    decisions = connection.execute(
        "SELECT * FROM decisions WHERE project_id=%s AND active AND NOT needs_review", (project_id,)
    ).fetchall()
    for decision in decisions:
        if any(
            s["id"] not in current or source_hash(s) != source_hash(current[s["id"]])
            for s in decision["evidence_basis"]
        ):
            connection.execute("UPDATE decisions SET needs_review=true WHERE id=%s", (decision["id"],))
            connection.execute(
                "INSERT INTO decision_events(project_id,decision) VALUES (%s,%s)",
                (
                    project_id,
                    Jsonb(
                        {
                            "id": decision["id"],
                            "event": "evidence_changed",
                            "needs_review": True,
                            "basis_snapshot_id": str(decision["basis_snapshot_id"]),
                        }
                    ),
                ),
            )
