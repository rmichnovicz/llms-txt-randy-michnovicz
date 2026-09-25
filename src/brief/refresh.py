from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any, Literal


def content_hash(title: str, description: str, content: str) -> str:
    normalized = [" ".join(value.split()) for value in [title, description, content]]
    return hashlib.sha256(json.dumps(normalized).encode()).hexdigest()


@dataclass
class StoredPage:
    url: str
    hash: str
    not_found_count: int = 0


@dataclass
class Observation:
    url: str
    outcome: Literal["ok", "not-found", "unavailable"]
    hash: str | None = None


def reconcile_pages(previous: list[StoredPage], observations: list[Observation]) -> dict[str, Any]:
    state = {p.url: replace(p) for p in previous}
    changes: dict[str, list[str]] = {"added": [], "modified": [], "removed": [], "unavailable": []}
    seen = set()
    for observation in observations:
        if observation.url in seen:
            raise ValueError("Duplicate observation in one crawl")
        seen.add(observation.url)
        old = state.get(observation.url)
        if observation.outcome == "ok":
            if not observation.hash:
                raise ValueError("Successful observation requires a hash")
            if not old:
                changes["added"].append(observation.url)
            elif old.hash != observation.hash:
                changes["modified"].append(observation.url)
            state[observation.url] = StoredPage(observation.url, observation.hash)
        elif observation.outcome == "not-found" and old:
            old.not_found_count += 1
            if old.not_found_count >= 2:
                del state[old.url]
                changes["removed"].append(old.url)
            else:
                changes["unavailable"].append(old.url)
        elif observation.outcome == "unavailable":
            changes["unavailable"].append(observation.url)
    return {
        "pages": sorted(state.values(), key=lambda p: p.url),
        **{key: sorted(value) for key, value in changes.items()},
        "changed": any(changes[key] for key in ["added", "modified", "removed"]),
    }


@dataclass
class RefreshState:
    has_published: bool
    source_changed: bool
    crawl_usable: bool
    auto_publish: bool
    has_unpublished_draft: bool
    published_manually_edited: bool
    has_conflict: bool
    candidate_valid: bool
    output_changed: bool


def refresh_action(state: RefreshState) -> Literal["preserve", "unchanged", "review", "publish"]:
    if not state.has_published or not state.crawl_usable:
        return "preserve"
    if not state.source_changed:
        return "unchanged"
    if not state.candidate_valid:
        return "preserve"
    if state.has_conflict:
        return "review"
    if not state.output_changed:
        return "unchanged"
    if not state.auto_publish or state.has_unpublished_draft or state.published_manually_edited:
        return "review"
    return "publish"
