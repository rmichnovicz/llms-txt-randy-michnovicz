"""Explicit publication of immutable versions and bounded existing-guide discovery."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from uuid import UUID

from psycopg.types.json import Jsonb

from brief.crawl.fetch import USER_AGENT, FetchError, SafeFetcher
from brief.crawl.runner import Scope
from brief.editor import EditConflict, locked_project

if TYPE_CHECKING:
    from brief.crawl.fetch import Response
    from brief.interfaces import Fetcher
    from brief.store import Store


def candidates(site_url: str) -> list[str]:
    scope = Scope(site_url)
    path = scope.path.rstrip("/")
    urls = []
    while True:
        urls.append(scope.origin + path + "/llms.txt")
        if not path:
            return urls
        path = path.rsplit("/", 1)[0]


def markdown(response: Response) -> str:
    """Reject HTML error pages and binary responses, even with a misleading MIME type."""
    if response.status != 200:
        raise FetchError(f"HTTP {response.status}")
    if any(t in response.content_type.lower() for t in ("html", "json", "image/", "application/pdf")):
        raise FetchError("Response is not a Markdown text file")
    try:
        text = response.body.decode("utf-8-sig").strip()
    except UnicodeDecodeError:
        raise FetchError("Response is not UTF-8 text") from None
    if "\x00" in text or not text.startswith("# ") or not text.splitlines()[0][2:].strip():
        raise FetchError("No Markdown title found")
    if "<html" in text.lower() or "<!doctype" in text.lower():
        raise FetchError("Response contains an HTML page")
    return text + "\n"


async def inspect(site_url: str, *, exact: bool = False, fetcher: Fetcher | None = None) -> dict[str, Any]:
    if fetcher is None:
        async with SafeFetcher(timeout=6, max_bytes=100_000) as transport:
            return await inspect(site_url, exact=exact, fetcher=transport)
    scope = Scope(site_url)
    urls = candidates(site_url)
    urls = urls[:1] if exact else urls
    report: dict[str, Any] = {"checked_at": datetime.now(UTC).isoformat(), "guides": [], "checks": [], "complete": True}

    def same_origin(url: str) -> bool:
        parsed = urlsplit(url)
        return f"{parsed.scheme}://{parsed.netloc}" == scope.origin

    try:
        async with asyncio.timeout(20):
            response = await fetcher.get(scope.origin + "/robots.txt", allowed=same_origin)
            policy = RobotFileParser()
            if response.status == 200:
                policy.parse(response.body.decode("utf-8", errors="replace").splitlines())
            elif response.status in {404, 410}:
                policy.parse([])
            else:
                raise FetchError(f"robots.txt unavailable (HTTP {response.status})")
            if delay := policy.crawl_delay(USER_AGENT):
                fetcher.interval = max(fetcher.interval, float(delay))

            def allowed(url: str) -> bool:
                return same_origin(url) and policy.can_fetch(USER_AGENT, url)

            for url in urls:
                try:
                    response = await fetcher.get(url, allowed=allowed)
                    text = markdown(response)
                    report["guides"].append(
                        {
                            "url": response.url,
                            "requested_url": url,
                            "markdown": text,
                            "sha256": hashlib.sha256(response.body).hexdigest(),
                        }
                    )
                    report["checks"].append({"url": url, "status": "found"})
                except FetchError as error:
                    report["checks"].append({"url": url, "status": str(error)})
    except (FetchError, TimeoutError) as error:
        report["complete"] = False
        report["error"] = str(error) or "Guide check exceeded its time budget. Try again."
    return report


def save_check(store: Store, project_id: UUID, report: dict[str, Any]) -> None:
    with store.db.connect() as connection:
        connection.execute("UPDATE projects SET existing_guide_check=%s WHERE id=%s", (Jsonb(report), project_id))


def publish(store: Store, project_id: UUID, revision: int, version_id: UUID | None) -> dict[str, Any]:
    with store.db.connect() as connection:
        project = locked_project(connection, project_id, revision)
        if connection.execute(
            "SELECT 1 FROM jobs WHERE project_id=%s AND kind<>'evaluate' AND status IN ('pending','running')",
            (project_id,),
        ).fetchone():
            raise EditConflict("Wait for the current update to finish before changing publication.")
        if version_id is not None:
            if version_id != project["draft_version_id"]:
                raise EditConflict("Publish the current saved draft. Reload before publishing.")
            version = connection.execute(
                "SELECT decisions_revision FROM document_versions WHERE id=%s AND project_id=%s",
                (version_id, project_id),
            ).fetchone()
            if (
                not version
                or version["decisions_revision"] != project["decisions_revision"]
                or connection.execute(
                    "SELECT 1 FROM decisions WHERE project_id=%s AND active AND needs_review",
                    (project_id,),
                ).fetchone()
            ):
                raise EditConflict("Resolve flagged answers and update the draft before publishing.")
        connection.execute(
            """UPDATE projects SET published_version_id=%s,
            published_at=CASE WHEN %s::uuid IS NULL THEN NULL ELSE now() END,
            revision=revision+1 WHERE id=%s""",
            (version_id, version_id, project_id),
        )
    return {"ok": True}
