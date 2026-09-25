from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from brief.crawl.runner import crawl
from brief.interfaces import Completer
from brief.model import ModelError
from brief.store import LeaseLost, Store

if TYPE_CHECKING:
    from brief.contracts import Source
    from brief.crawl.runner import CrawlResult
    from brief.interfaces import Generator
    from brief.live import LiveProgress


logger = logging.getLogger(__name__)


async def run_once(
    store: Store,
    *,
    crawler: Callable[..., Awaitable[CrawlResult]] = crawl,
    generator: Generator | None = None,
    live: LiveProgress | None = None,
) -> bool:
    job = await asyncio.to_thread(store.claim)
    if not job:
        return False

    recent = []
    started = datetime.now(UTC).isoformat()
    saved_stage = None

    async def report(data: dict[str, Any]) -> None:
        nonlocal saved_stage
        entry: dict[str, Any] = {**data, "at": datetime.now(UTC).isoformat()}
        recent.append(entry)
        del recent[:-6]
        progress: dict[str, Any] = {**entry, "started_at": started, "recent": recent[:]}
        if live is None or data.get("stage") != saved_stage:
            await asyncio.to_thread(store.report_progress, job, progress)
            saved_stage = data.get("stage")
        if live is not None:
            live.progress(job, progress)

    async def work() -> None:
        if job["kind"] == "evaluate":
            from brief.guide_tests import run

            if generator is None:
                raise ModelError("Model provider is not configured")
            if not isinstance(generator, Completer):
                raise ModelError("Model provider does not support structured completion")
            await run(store, job, generator, report)
            return
        if job["kind"] == "generate":
            if generator is None:
                raise ModelError("Model provider is not configured")
            context = await asyncio.to_thread(store.generation_context, job)
            await report(
                {
                    "stage": "writing",
                    "message": f"Shaping the guide from {len(context.sources)} pages and {len(context.decisions)} saved decisions.",
                    "pages_read": len(context.sources),
                }
            )
            from brief.model_cache import generate

            completion = await asyncio.to_thread(generate, store, job, generator, context)
            await report(
                {
                    "stage": "checking",
                    "message": "Reused an identical validated model result; checking source references."
                    if completion.metadata.get("cache", {}).get("status") == "hit"
                    else "Checking the document, source references, and suggested questions.",
                }
            )
            summary = await asyncio.to_thread(store.finish_generation, job, context, completion)
            logger.info("generation_finished job=%s status=%s", job["id"], summary["status"])
            return
        project, previous = await asyncio.to_thread(store.crawl_context, job)
        await report({"stage": "discovering", "message": "Finding the pages that will make this guide useful."})
        options: dict[str, Any] = {"progress": report} if crawler is crawl else {}
        if crawler is crawl:
            from brief.crawl.cache import PageCache

            options["cache"] = PageCache(store.db, project["site_id"])
            from brief.crawl.inventory import load

            options["discovery_state"] = await asyncio.to_thread(load, store.db, project["id"])
        if crawler is crawl and isinstance(generator, Completer):
            from brief.crawl.planning import assess

            with store.db.connect() as connection:
                direction = connection.execute(
                    "SELECT kind,statement FROM decisions WHERE project_id=%s AND active ORDER BY kind,statement",
                    (project["id"],),
                ).fetchall()
                direction_changed = (
                    previous is not None
                    and connection.execute(
                        "SELECT EXISTS(SELECT 1 FROM decision_events WHERE project_id=%s AND created_at > %s) AS changed",
                        (project["id"], previous["created_at"]),
                    ).fetchone()["changed"]
                )

            if project.get("guide_purpose"):
                direction.append({"kind": "preference", "statement": project["guide_purpose"]})

            async def assessor(sources: list[Source], candidates: list[str]) -> dict[str, Any]:
                plan = await asyncio.to_thread(assess, generator, sources, candidates, direction)
                return {**plan, "direction": direction, "reused": False}

            plan = previous["coverage"].get("assessment") if previous else None
            # Legacy plans predate the stored direction. Decision events let us
            # reuse them only when owner direction has not changed since the crawl.
            if plan is not None and (plan["direction"] == direction if "direction" in plan else not direction_changed):
                options["saved_plan"] = {**plan, "direction": direction}
            else:
                options["assessor"] = assessor
        result = await crawler(
            project["site_url"], [s["url"] for s in previous["sources"]] if previous else [], **options
        )
        if crawler is crawl and project.get("existing_guide_check") is None:
            from brief.publication import inspect, save_check

            await report({"stage": "discovering", "message": "Checking for an existing llms.txt guide."})
            guide_check = await inspect(project["site_url"])
            await asyncio.to_thread(save_check, store, project["id"], guide_check)
        await report(
            {
                "stage": "saving",
                "message": f"Collected {len(result.sources)} readable pages. Comparing them with the previous snapshot.",
                "pages_read": len(result.sources),
            }
        )
        summary = await asyncio.to_thread(store.finish_crawl, job, result, enqueue_generation=generator is not None)
        logger.info("crawl_finished job=%s status=%s", job["id"], summary["status"])

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(30)
            if not await asyncio.to_thread(store.renew, job):
                raise LeaseLost("Job lease expired or was reclaimed")

    work_task, heartbeat_task = asyncio.create_task(work()), asyncio.create_task(heartbeat())
    try:
        done, _ = await asyncio.wait([work_task, heartbeat_task], return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            await task
    except LeaseLost:
        logger.warning("lease_lost job=%s", job["id"])
    except ModelError as error:
        try:
            await asyncio.to_thread(store.fail, job, str(error), retryable=error.retryable)
        except LeaseLost:
            pass
    except Exception as error:  # noqa: BLE001 - durable job boundary must persist unexpected failures
        logger.error("crawl_failed job=%s error_type=%s", job["id"], type(error).__name__)
        try:
            await asyncio.to_thread(store.fail, job, f"Worker error ({type(error).__name__})")
        except LeaseLost:
            pass
    finally:
        work_task.cancel()
        heartbeat_task.cancel()
        await asyncio.gather(work_task, heartbeat_task, return_exceptions=True)
        if live is not None:
            live.invalidate(job["project_id"])
    return True


async def run_forever(store: Store, *, generator: Generator | None = None, live: LiveProgress | None = None) -> None:
    while True:
        if not await run_once(store, generator=generator, live=live):
            await asyncio.sleep(2)
