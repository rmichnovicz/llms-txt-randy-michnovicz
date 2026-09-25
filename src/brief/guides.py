"""Path-scoped guide operations. Decisions and history remain per guide."""

from __future__ import annotations

import io
import posixpath
import zipfile
from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4

from psycopg import Connection

from brief.crawl.fetch import normalize_url
from brief.editor import EditConflict

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


def linked_markdown(c: Connection[dict[str, Any]], project: dict[str, Any], markdown: str) -> str:
    """Add only ready child links; do not advertise a file which does not exist yet."""
    children = c.execute(
        """SELECT guide_path,guide_name FROM projects WHERE site_id=%s AND id<>%s
        AND draft_version_id IS NOT NULL AND NOT auto_cancelled ORDER BY guide_path""",
        (project["site_id"], project["id"]),
    ).fetchall()
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


def link_ready_child(c: Connection[dict[str, Any]], child: dict[str, Any]) -> None:
    if child["guide_path"] == "/":
        return
    root = c.execute(
        "SELECT * FROM projects WHERE site_id=%s AND guide_path='/' FOR UPDATE", (child["site_id"],)
    ).fetchone()
    if not root or not root["draft_version_id"]:
        return
    # Do not invalidate a root generation in flight. Its completion adds ready links.
    if c.execute(
        "SELECT 1 FROM jobs WHERE project_id=%s AND status IN ('pending','running') AND kind='generate'", (root["id"],)
    ).fetchone():
        return
    for pointer in ("draft_version_id", "proposal_version_id"):
        if not root[pointer]:
            continue
        old = c.execute("SELECT * FROM document_versions WHERE id=%s", (root[pointer],)).fetchone()
        assert old is not None
        markdown = linked_markdown(c, root, old["markdown"])
        if markdown == old["markdown"]:
            continue
        vid = uuid4()
        c.execute(
            """INSERT INTO document_versions(id,project_id,snapshot_id,kind,generation_input,structured_result,
            markdown,model_metadata,manually_edited,decisions_revision)
            SELECT %s,project_id,snapshot_id,kind,generation_input,structured_result,%s,
            '{"origin":"related-guide-link"}'::jsonb,manually_edited,decisions_revision FROM document_versions WHERE id=%s""",
            (vid, markdown, old["id"]),
        )
        # Pointer names are constants from the tuple above, never external input.
        c.execute(f"UPDATE projects SET {pointer}=%s,revision=revision+1 WHERE id=%s", (vid, root["id"]))


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
