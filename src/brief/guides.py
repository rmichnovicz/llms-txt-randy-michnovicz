"""Path-scoped guide operations. Decisions and history remain per guide."""

from __future__ import annotations

import io
import posixpath
import zipfile
from collections import Counter
from collections.abc import Collection, Iterable
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4

from psycopg import Connection

from brief.contracts import GenerationResult, Source
from brief.corpus import canonical_url, parse_file
from brief.crawl.fetch import normalize_url
from brief.editor import EditConflict
from brief.generation import render_guide, safe_destination

if TYPE_CHECKING:
    from brief.store import Store


def covering_guide(url: str, guides: Iterable[str]) -> str | None:
    page = urlsplit(normalize_url(url))
    applicable = []
    for guide in guides:
        file = urlsplit(normalize_url(guide))
        scope = posixpath.dirname(file.path).rstrip("/") + "/"
        if (page.scheme, page.netloc) == (file.scheme, file.netloc) and (
            page.path == scope.rstrip("/") or page.path.startswith(scope)
        ):
            applicable.append((len(scope), guide))
    return max(applicable)[1] if applicable else None


def normalize_scope(path: str) -> str:
    if not path.startswith("/") or path.startswith("//") or any(c in path for c in ["?", "#", "\\"]):
        raise EditConflict("Use a site path such as /help/.")
    decoded = unquote(path)
    if "\\" in decoded or "%2f" in path.lower() or "//" in decoded:
        raise EditConflict("Use a path without encoded separators or empty segments.")
    if any(segment in {".", ".."} for segment in decoded.split("/")) or any(ord(c) < 33 for c in decoded):
        raise EditConflict("Use a path without traversal or control characters.")
    return "/" + path.strip("/") + "/" if path.strip("/") else "/"


def suggestions(sources: list[dict[str, Any]], guides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = {g["guide_path"] for g in guides}
    groups: Counter[str] = Counter()
    for source in sources:
        parts = urlsplit(source["url"]).path.strip("/").split("/")
        if len(parts) > 1 and parts[0] in {"docs", "help", "support", "blog", "learn", "products", "developers"}:
            groups["/" + parts[0] + "/"] += 1
    return [
        {
            "path": path,
            "name": path.strip("/").replace("-", " ").title(),
            "purpose": f"Help readers navigate {path} independently of the site overview.",
            "reason": f"{count} captured pages form a distinct section under {path}.",
        }
        for path, count in groups.most_common()
        if count >= 3 and path not in existing
    ][:3]


def create_guide(store: Store, project_id: UUID, *, path: str, name: str, purpose: str) -> dict[str, Any]:
    path = normalize_scope(path)
    with store.db.connect() as c:
        parent = c.execute("SELECT * FROM projects WHERE id=%s", (project_id,)).fetchone()
        assert parent is not None
        site = c.execute("SELECT * FROM sites WHERE id=%s FOR UPDATE", (parent["site_id"],)).fetchone()
        assert site is not None
        if c.execute("SELECT 1 FROM projects WHERE site_id=%s AND guide_path=%s", (site["id"], path)).fetchone():
            raise EditConflict("There is already a guide for this path.")
        url = normalize_url(site["url"].rstrip("/") + path)
        project = c.execute(
            """INSERT INTO projects(id,site_id,site_url,guide_path,guide_name,guide_purpose,management_token_hash)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (uuid4(), site["id"], url, path, name, purpose, parent["management_token_hash"]),
        ).fetchone()
        assert project is not None
        store._enqueue(c, project, f"initial:{project['id']}", "initial_crawl")
        return {"id": project["id"]}


def bundle(store: Store, site_id: UUID) -> bytes:
    with store.db.connect() as c:
        guides = c.execute(
            """SELECT p.guide_path,p.guide_name,d.markdown FROM projects p
        LEFT JOIN document_versions d ON d.id=p.draft_version_id WHERE p.site_id=%s AND NOT p.auto_cancelled ORDER BY p.guide_path""",
            (site_id,),
        ).fetchall()
    if any(g["markdown"] is None for g in guides):
        raise EditConflict("Wait for every guide to have a draft before downloading the bundle.")
    for guide in guides:
        normalize_scope(guide["guide_path"])
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for guide in guides:
            text = guide["markdown"]
            children = [
                g
                for g in guides
                if g["guide_path"] != guide["guide_path"]
                and g["guide_path"].startswith(guide["guide_path"])
                and g["guide_path"] + "llms.txt" not in text
            ]
            if children:
                text += "\n## Related guides\n\n"
                for child in children:
                    if child["guide_path"] + "llms.txt" in text:
                        continue
                    target = posixpath.relpath(child["guide_path"] + "llms.txt", guide["guide_path"])
                    label = child["guide_name"].replace("[", "").replace("]", "").replace("\n", " ")
                    text += f"- [{label}](<{target}>): Guide to {child['guide_path']}\n"
            archive.writestr(guide["guide_path"].lstrip("/") + "llms.txt", text)
    return output.getvalue()


def plan_automatic(
    store: Store, c: Connection[dict[str, Any]], parent: dict[str, Any], sources: list[dict[str, Any]]
) -> None:
    """Queue section work atomically with the first usable root draft; never recurse."""
    if parent["guide_path"] != "/" or parent["auto_guides_planned"]:
        return
    c.execute("SELECT id FROM sites WHERE id=%s FOR UPDATE", (parent["site_id"],))
    c.execute("UPDATE projects SET auto_guides_planned=true WHERE id=%s", (parent["id"],))
    existing = c.execute("SELECT guide_path FROM projects WHERE site_id=%s", (parent["site_id"],)).fetchall()
    eligible = {"docs", "help", "support", "developers", "learn"}
    section_sources = [s for s in sources if urlsplit(s["url"]).path.strip("/").split("/")[0] in eligible]
    for suggestion in suggestions(section_sources, existing):
        url = normalize_url(parent["site_url"].rstrip("/") + suggestion["path"])
        child = c.execute(
            """INSERT INTO projects(id,site_id,site_url,guide_path,guide_name,guide_purpose,
            management_token_hash,auto_reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (
                uuid4(),
                parent["site_id"],
                url,
                suggestion["path"],
                suggestion["name"],
                suggestion["purpose"],
                parent["management_token_hash"],
                suggestion["reason"],
            ),
        ).fetchone()
        assert child is not None
        store._enqueue(c, child, f"initial:{child['id']}", "initial_crawl")


def cancel_automatic(store: Store, project_id: UUID) -> dict[str, Any]:
    from brief.editor import supersede

    with store.db.connect() as c:
        p = c.execute("SELECT * FROM projects WHERE id=%s FOR UPDATE", (project_id,)).fetchone()
        assert p is not None
        if not p["auto_reason"] or p["draft_version_id"]:
            raise EditConflict("Only an unfinished automatic guide can be cancelled.")
        supersede(c, project_id)
        c.execute("UPDATE projects SET auto_cancelled=true, revision=revision+1 WHERE id=%s", (project_id,))
    return {"status": "cancelled"}


def retained_destinations(
    c: Connection[dict[str, Any]], project: dict[str, Any], result: GenerationResult, sources: list[Source]
) -> set[str]:
    """Parent entry points that stay direct even when a child repeats them.

    Owner-directed shortcuts are honoured only while their direction is still active, so
    removing an answer releases the link without waiting for a regeneration to succeed.
    Shortcuts with no cited direction are the model's own parent-level editorial choice.
    """
    if not result.guide or not result.guide.shortcuts:
        return set()
    active = {
        row["id"]
        for row in c.execute("SELECT id FROM decisions WHERE project_id=%s AND active", (project["id"],)).fetchall()
    }
    if project.get("guide_purpose"):
        active.add("guide_purpose")  # The saved purpose is supplied as direction, not a stored row.
    by_id = {source.id: source for source in sources}
    kept = set()
    for shortcut in result.guide.shortcuts:
        source = by_id.get(shortcut.source_id)
        # Stored results outlive both their source snapshot and their owner direction.
        if source is None or not set(shortcut.decision_ids) <= active:
            continue
        try:
            kept.add(canonical_url(safe_destination(source.markdown_url or source.url)))
        except ValueError:
            continue
    return kept


def consolidate_links(
    markdown: str, base_url: str, children: list[dict[str, Any]], retained: Collection[str] = ()
) -> str:
    """Delegate repeated detail links only when a child lists them and the parent does not need them."""
    delegated = set()
    origin = urlsplit(base_url)
    for child in children:
        child_url = f"{origin.scheme}://{origin.netloc}{child['guide_path']}llms.txt"
        for link in parse_file(child["markdown"], child_url)["links"]:
            page = urlsplit(link["canonical"])
            if (
                (page.scheme, page.netloc) == (origin.scheme, origin.netloc)
                and page.path.startswith(child["guide_path"])
                and page.path.rstrip("/") != child["guide_path"].rstrip("/")
                and not page.path.endswith("/llms.txt")
            ):
                delegated.add(link["canonical"])
    parsed = parse_file(markdown, base_url)
    lines = markdown.splitlines(keepends=True)
    removed = {
        link["line"] - 1
        for link in parsed["links"]
        if link["canonical"] in delegated
        and link["canonical"] not in retained
        and lines[link["line"] - 1].startswith("- [")
    }
    if not removed:
        return markdown
    headings = parsed["headings"]
    for i, heading in enumerate(headings):
        start = heading["line"] - 1
        end = headings[i + 1]["line"] - 1 if i + 1 < len(headings) else len(lines)
        if heading["level"] == 2 and not any(lines[n].strip() for n in range(start + 1, end) if n not in removed):
            removed.update(range(start, end))
    return "".join(line for n, line in enumerate(lines) if n not in removed)


def linked_markdown(
    c: Connection[dict[str, Any]],
    project: dict[str, Any],
    markdown: str,
    *,
    manually_edited: bool = False,
    retained: Collection[str] = (),
) -> str:
    """Add only ready child links; do not advertise a file which does not exist yet."""
    children = c.execute(
        """SELECT p.guide_path,p.guide_name,d.markdown FROM projects p
        JOIN document_versions d ON d.id=p.draft_version_id WHERE p.site_id=%s AND p.id<>%s
        AND NOT p.auto_cancelled ORDER BY p.guide_path""",
        (project["site_id"], project["id"]),
    ).fetchall()
    children = [child for child in children if child["guide_path"].startswith(project["guide_path"])]
    if not manually_edited:
        markdown = consolidate_links(markdown, project["site_url"], children, retained)
    origin = urlsplit(project["site_url"])
    lines = []
    for child in children:
        if not child["guide_path"].startswith(project["guide_path"]):
            continue
        url = f"{origin.scheme}://{origin.netloc}{child['guide_path']}llms.txt"
        if url in markdown:
            continue
        label = child["guide_name"].replace("[", "").replace("]", "").replace("\n", " ")
        lines.append(f"- [{label}](<{url}>): Guide to {child['guide_path']}")
    return markdown + "\n## Related guides\n\n" + "\n".join(lines) + "\n" if lines else markdown


def reconcile_parent(c: Connection[dict[str, Any]], parent: dict[str, Any]) -> None:
    """Recheck one parent's coverage against its ready children, as new immutable versions."""
    # Do not invalidate a parent generation in flight. Its completion adds ready links.
    if c.execute(
        "SELECT 1 FROM jobs WHERE project_id=%s AND status IN ('pending','running') AND kind='generate'",
        (parent["id"],),
    ).fetchone():
        return
    for pointer in ("draft_version_id", "proposal_version_id"):
        if not parent[pointer]:
            continue
        old = c.execute("SELECT * FROM document_versions WHERE id=%s", (parent[pointer],)).fetchone()
        assert old is not None
        markdown = old["markdown"]
        retained: Collection[str] = ()
        if not old["manually_edited"]:
            # Retain the original structured guide so links can return if a child
            # stops covering them. Saved versions themselves remain immutable.
            result = GenerationResult.model_validate(old["structured_result"])
            assert result.guide is not None
            sources = [Source.model_validate(s) for s in old["generation_input"]["sources"]]
            markdown = render_guide(result.guide, sources)
            retained = retained_destinations(c, parent, result, sources)
        markdown = linked_markdown(c, parent, markdown, manually_edited=old["manually_edited"], retained=retained)
        if markdown == old["markdown"]:
            continue
        vid = uuid4()
        # Carry refined_from_version_id too: relinking is not a refinement, and dropping it
        # would hide the before/after comparison the owner is still reviewing.
        c.execute(
            """INSERT INTO document_versions(id,project_id,snapshot_id,kind,generation_input,structured_result,
            markdown,model_metadata,manually_edited,decisions_revision,refined_from_version_id)
            SELECT %s,project_id,snapshot_id,kind,generation_input,structured_result,%s,
            '{"origin":"related-guide-link"}'::jsonb,manually_edited,decisions_revision,refined_from_version_id
            FROM document_versions WHERE id=%s""",
            (vid, markdown, old["id"]),
        )
        # Pointer names are constants from the tuple above, never external input.
        c.execute(f"UPDATE projects SET {pointer}=%s,revision=revision+1 WHERE id=%s", (vid, parent["id"]))


def link_ready_child(c: Connection[dict[str, Any]], child: dict[str, Any]) -> None:
    """Reconcile every ancestor guide, not only the root, so intermediate guides stay usable."""
    if child["guide_path"] == "/":
        return
    paths = [
        row["guide_path"]
        for row in c.execute(
            "SELECT guide_path FROM projects WHERE site_id=%s AND id<>%s AND draft_version_id IS NOT NULL",
            (child["site_id"], child["id"]),
        ).fetchall()
        if child["guide_path"].startswith(row["guide_path"])
    ]
    # Lock deepest first: callers already hold the descendant, so the order stays consistent.
    for path in sorted(paths, key=len, reverse=True):
        parent = c.execute(
            "SELECT * FROM projects WHERE site_id=%s AND guide_path=%s FOR UPDATE", (child["site_id"], path)
        ).fetchone()
        if parent and parent["draft_version_id"]:
            reconcile_parent(c, parent)


def resume_automatic(store: Store, project_id: UUID) -> dict[str, Any]:
    with store.db.connect() as c:
        p = c.execute("SELECT * FROM projects WHERE id=%s FOR UPDATE", (project_id,)).fetchone()
        assert p is not None
        if not p["auto_cancelled"]:
            raise EditConflict("This guide is not cancelled.")
        c.execute("UPDATE projects SET auto_cancelled=false,revision=revision+1 WHERE id=%s", (project_id,))
        p["revision"] += 1
        job = store._enqueue(c, p, f"resume-guide:{uuid4()}", "initial_crawl")
    return {"job_id": job["id"]}
