from __future__ import annotations

from typing import Any

from brief.change_inbox import build


def test_diff_tracks_saved_draft_not_last_refresh_and_handles_add_remove() -> None:
    def source(sid: str, content: str) -> dict[str, Any]:
        return {"id": sid, "url": f"https://example.com/{sid}", "title": sid, "description": "", "content": content}

    old = source("pricing", "Twenty dollars")
    new = source("pricing", "Thirty dollars")
    p: dict[str, Any] = {
        "draft": {
            "generation_input": {"sources": [old, source("retired", "Old")]},
            "structured_result": {"guide": {"sections": [{"title": "Plans", "links": [{"source_id": "pricing"}]}]}},
        },
        "snapshot": {"sources": [new, source("new", "New")]},
        "decisions": [{"id": "owner", "active": True, "needs_review": True, "evidence_basis": [old]}],
    }
    changes = {x["id"]: x for x in build(p)}
    assert changes["pricing"]["sections"] == ["Plans"]
    assert changes["pricing"]["decision_ids"] == ["owner"]
    assert "-Twenty dollars" in changes["pricing"]["diff"]
    assert "+Thirty dollars" in changes["pricing"]["diff"]
    assert changes["retired"]["kind"] == "removed"
    assert changes["new"]["kind"] == "added"
    p["draft"]["generation_input"]["sources"] = p["snapshot"]["sources"]
    assert build(p) == []
