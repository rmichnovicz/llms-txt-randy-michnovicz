from __future__ import annotations

import asyncio
import json
import posixpath
import time
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from brief.contracts import Source
from brief.crawl.extract import EXTRACTION_VERSION, extract_page, source_id
from brief.crawl.fetch import FETCH_CONCURRENCY, USER_AGENT, BlockedRedirect, FetchError, SafeFetcher, normalize_url
from brief.crawl.inventory import balanced, section
from brief.crawl.planning import priority
from brief.refresh import Observation, content_hash

if TYPE_CHECKING:
    from brief.crawl.cache import PageCache
    from brief.crawl.fetch import Response
    from brief.interfaces import Fetcher, Progress, URLPolicy


@dataclass
class CrawlResult:
    sources: list[Source] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    attempted: int = 0
    discovered: int = 0
    truncated: bool = False
    extraction_version: str = EXTRACTION_VERSION
    stop_reason: str = "exhausted"
    downloaded_bytes: int = 0
    discovery_state: dict[str, Any] | None = None
    sitemap_discovery: dict[str, Any] | None = None
    assessment: dict[str, Any] | None = None
    unread: int = 0
    cache_hits: int = 0
    conditional_requests: int = 0
    duration_ms: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "sources": [source.model_dump() for source in self.sources]}


class Scope:
    def __init__(self, url: str) -> None:
        self.url = normalize_url(url)
        parsed = urlsplit(self.url)
        self.host = (parsed.hostname or "").removeprefix("www.")
        path = posixpath.normpath(unquote(parsed.path))
        self.path = (
            posixpath.dirname(path) if not parsed.path.endswith("/") and "." in path.rsplit("/", 1)[-1] else path
        )
        self.origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))

    def same_site(self, url: str) -> bool:
        return (urlsplit(url).hostname or "").removeprefix("www.") == self.host

    def contains(self, url: str) -> bool:
        path = posixpath.normpath(unquote(urlsplit(url).path))
        return self.same_site(url) and (self.path == "/" or path == self.path or path.startswith(self.path + "/"))


async def crawl(
    site_url: str,
    previous_urls: Sequence[str] = (),
    *,
    max_pages: int | None = None,
    deadline: float = 120,
    fetcher: Fetcher | None = None,
    progress: Progress | None = None,
    assessor: Callable[[list[Source], list[str]], Awaitable[dict[str, Any]]] | None = None,
    saved_plan: dict[str, Any] | None = None,
    cache: PageCache | None = None,
    initial_batch: int = 8,
    byte_budget: int = 50_000_000,
    text_budget: int = 300_000,
    discovery_state: dict[str, Any] | None = None,
    inventory_byte_budget: int = 4_000_000,
) -> CrawlResult:
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive when explicitly supplied")
    if initial_batch < 1 or byte_budget < 1 or text_budget < 1:
        raise ValueError("Crawl budgets must be positive")
    if fetcher is None:
        async with SafeFetcher() as transport:
            return await crawl(
                site_url,
                previous_urls,
                max_pages=max_pages,
                deadline=deadline,
                fetcher=transport,
                progress=progress,
                assessor=assessor,
                saved_plan=saved_plan,
                cache=cache,
                initial_batch=initial_batch,
                byte_budget=byte_budget,
                text_budget=text_budget,
                discovery_state=discovery_state,
                inventory_byte_budget=inventory_byte_budget,
            )
    started_at = time.monotonic()
    scope = Scope(site_url)
    result = CrawlResult()
    queue: deque[str] = deque()
    queued: set[str] = set()
    visited: set[str] = set()
    policies = {}
    policy_lock = asyncio.Lock()
    prefetched: dict[str, tuple[dict[str, Any] | None, Response | None] | BaseException] = {}
    previous = set(previous_urls)
    assessed = saved_plan is not None
    selected = (set(saved_plan["urls"]) | previous | {scope.url}) if saved_plan is not None else None
    target_order = (
        {url: i for i, url in enumerate(dict.fromkeys([scope.url, *saved_plan["urls"], *sorted(previous)]))}
        if saved_plan is not None
        else {}
    )
    if saved_plan is not None:
        result.assessment = {**saved_plan, "reused": True}
        result.assessment.pop("metadata", None)  # No model usage incurred by this refresh.

    text_size = 0
    inventory_bytes = 0
    inventory_full = False
    section_reads: dict[str, int] = {}
    sitemaps: list[str] = []
    sitemap_offsets = {}
    resumed = (discovery_state or {}).get("sitemaps", {})

    class DownloadBudget(Exception):
        pass

    async def fetch(url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
        if result.downloaded_bytes >= byte_budget:
            raise DownloadBudget("Download budget reached")
        response = await fetcher.get(url, allowed=allowed, **({"headers": headers} if headers else {}))
        result.downloaded_bytes += len(response.body)
        if result.downloaded_bytes > byte_budget:
            raise DownloadBudget("Download budget reached")
        return response

    async def robots_for(url: str) -> RobotFileParser:
        parsed = urlsplit(url)
        origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        async with policy_lock:
            if origin not in policies:
                response = await fetch(origin + "/robots.txt", allowed=scope.same_site)
                policy = RobotFileParser()
                if response.status == 200:
                    policy.parse(response.body.decode("utf-8", errors="replace").splitlines())
                elif response.status in {404, 410}:
                    policy.parse([])
                else:
                    raise FetchError(f"robots.txt unavailable (HTTP {response.status}); crawl deferred")
                delay = policy.crawl_delay(USER_AGENT)
                if delay:
                    fetcher.interval = max(fetcher.interval, float(delay))
                policies[origin] = policy
            return policies[origin]

    def enqueue(url: str) -> bool | None:
        nonlocal inventory_bytes, inventory_full
        try:
            url = normalize_url(url)
        except ValueError:
            return None
        if (
            url not in queued
            and scope.contains(url)
            and not urlsplit(url)
            .path.lower()
            .endswith((".pdf", ".png", ".jpg", ".jpeg", ".svg", ".gif", ".zip", ".css", ".js", ".xml", ".mp4"))
        ):
            cost = (
                len(json.dumps(url, ensure_ascii=False).encode()) + 1 if url not in previous and url != scope.url else 0
            )
            if inventory_bytes + cost > inventory_byte_budget:
                inventory_full = True
                result.truncated = True
                return False
            inventory_bytes += cost
            queued.add(url)
            if selected is None or url in selected or url in previous:
                queue.append(url)
        return True

    enqueue(scope.url)
    for url in previous_urls:
        enqueue(url)

    for url in saved_plan["urls"] if saved_plan is not None else []:
        enqueue(url)

    for url in (discovery_state or {}).get("urls", []):
        enqueue(url)

    async def permitted(url: str) -> bool:
        return scope.contains(url) and (await robots_for(url)).can_fetch(USER_AGENT, url)

    async def report(message: str, url: str | None = None) -> None:
        if progress:
            await progress(
                {
                    "stage": "reading",
                    "message": message,
                    "url": url,
                    "pages_read": len(result.sources),
                    "pages_found": len(queued),
                    "attempted": result.attempted,
                }
            )

    async def read_page(url: str) -> tuple[dict[str, Any] | None, Response | None]:
        if not await permitted(url):
            return None, None
        cached = await asyncio.to_thread(cache.get, url) if cache else None
        validators = {}
        if cached:
            if cached["etag"]:
                validators["If-None-Match"] = cached["etag"]
            elif cached["last_modified"]:
                validators["If-Modified-Since"] = cached["last_modified"]
        if validators:
            result.conditional_requests += 1
        return cached, await fetch(url, allowed=permitted, headers=validators)

    def page_rank(url: str, reads: dict[str, int]) -> tuple[int, tuple[int, int, str]] | tuple[int, int, str]:
        return (
            (-1 if url == scope.url else reads.get(section(url, scope.url), 0), priority(url, scope.url, previous))
            if selected is None
            else (0, target_order.get(url, 0), url)
        )

    current = None
    try:
        async with asyncio.timeout(deadline):
            await report("Checking the site’s crawling rules and sitemap.")
            robots = await robots_for(scope.url)
            # Discover relevant paths before applying the URL budget. Index requests
            # share the crawl's network protections and have their own time/byte budget.
            sitemaps, sitemap_seen, sitemap_known = [], set(), set()
            sitemap_bytes = 0
            sitemap_inventory_bytes = 0
            sitemap_trace = []
            discovery_stop = "exhausted"

            def add_sitemap(url: str) -> bool | None:
                nonlocal sitemap_inventory_bytes
                try:
                    url = normalize_url(url)
                    if not scope.same_site(url) or url in sitemap_known:
                        return None
                    if sitemap_inventory_bytes + len(url.encode()) + 8 > 1_000_000:
                        result.truncated = True
                        return False
                    sitemap_inventory_bytes += len(url.encode()) + 8
                    sitemap_known.add(url)
                    sitemaps.append(url)
                except ValueError:
                    return None
                return None

            def sitemap_rank(url: str) -> tuple[bool, int, int, str]:
                path = urlsplit(url).path.lower()
                tokens = scope.path.strip("/").lower().split("/")
                return (
                    url not in resumed,
                    0 if scope.path != "/" and scope.contains(url) else 1 if any(t in path for t in tokens if t) else 2,
                    len(path.split("/")),
                    path,
                )

            for url, offset in resumed.items():
                add_sitemap(url)
                sitemap_offsets[url] = offset
            for url in robots.site_maps() or [scope.origin + "/sitemap.xml"]:
                add_sitemap(url)
            try:
                async with asyncio.timeout(10):
                    while sitemaps:
                        if inventory_full or sitemap_bytes >= 4_000_000:
                            discovery_stop = "inventory_byte_budget" if inventory_full else "byte_budget"
                            result.truncated = True
                            break
                        sitemap = min(sitemaps, key=sitemap_rank)
                        sitemaps.remove(sitemap)
                        sitemap_seen.add(sitemap)
                        try:
                            response = await fetch(sitemap, allowed=scope.same_site)
                            sitemap_bytes += len(response.body)
                            sitemap_trace.append(
                                {"url": sitemap, "status": response.status, "bytes": len(response.body)}
                            )
                            if response.status != 200:
                                continue
                            root = fromstring(response.body)
                            is_index = root.tag.rsplit("}", 1)[-1] == "sitemapindex"
                            locations = [
                                el.text.strip() for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "loc" and el.text
                            ]
                            start_offset = sitemap_offsets.pop(sitemap, 0)
                            for index, location in enumerate(locations[start_offset:], start_offset):
                                accepted = add_sitemap(location) if is_index else enqueue(location)
                                if accepted is False:
                                    sitemap_offsets[sitemap] = index
                                    sitemaps.append(sitemap)
                                    discovery_stop = "inventory_byte_budget"
                                    break
                            if discovery_stop == "inventory_byte_budget":
                                break
                        except (FetchError, ParseError, DefusedXmlException) as error:
                            result.warnings.append(
                                {"url": sitemap, "reason": f"Sitemap unavailable ({type(error).__name__})"}
                            )
            except TimeoutError:
                if sitemap not in sitemaps:
                    sitemaps.append(sitemap)
                discovery_stop = "time_budget"
                result.truncated = True
            if inventory_full:
                discovery_stop = "inventory_byte_budget"
            result.sitemap_discovery = {
                "inventory_bytes": inventory_bytes,
                "resumed_urls": len((discovery_state or {}).get("urls", [])),
                "resumed_indexes": len(resumed),
                "fetches": len(sitemap_seen),
                "bytes": sitemap_bytes,
                "stop_reason": discovery_stop,
                "remaining_indexes": len(sitemaps),
                "trace": sitemap_trace,
            }
            if saved_plan is not None:
                await report("Reusing the saved page selection; checking those pages for changes.")
            while queue:
                if max_pages is not None and result.attempted >= max_pages:
                    result.stop_reason = "explicit_page_budget"
                    break
                if assessor and not assessed and len(result.sources) >= initial_batch:
                    assessed = True
                    await report("Assessing coverage and choosing what is worth reading next.")
                    candidates = balanced(set(queue) - visited, scope.url, previous)
                    try:
                        plan = await assessor(result.sources, candidates)
                        if set(plan["urls"]) - set(candidates):
                            raise ValueError("Planner returned an unknown URL")
                        selected = set(plan["urls"]) | previous
                        target_order = {url: i for i, url in enumerate(plan["urls"])}
                        result.assessment = {
                            **plan,
                            "candidate_count": len(candidates),
                            "inventory_candidates": len(set(queue) - visited),
                            "candidate_selection": "Section-balanced shortlist within 24 KB; omitted URLs remain in the saved inventory.",
                            "skipped_urls": [u for u in candidates if u not in selected],
                        }
                        queue = deque(u for u in queue if u in selected and u not in visited)
                        await report(plan["reason"])
                    except (ValueError, OSError) as error:
                        result.warnings.append(
                            {
                                "url": scope.url,
                                "reason": f"Coverage assessment unavailable ({type(error).__name__}); continuing ranked discovery.",
                            }
                        )
                    if not queue:
                        result.stop_reason = "coverage_plan_finished"
                        break
                if not prefetched:
                    # Bound each batch at planner/page-budget boundaries. Commit results in
                    # selection order so network timing cannot change the resulting guide.
                    count = (
                        min(FETCH_CONCURRENCY, max_pages - result.attempted)
                        if max_pages is not None
                        else FETCH_CONCURRENCY
                    )
                    if assessor and not assessed:
                        count = min(count, initial_batch - len(result.sources))
                    pending = set(queue) - visited
                    reads = dict(section_reads)
                    batch: list[str] = []
                    while pending and len(batch) < count:
                        url = min(pending, key=lambda u: page_rank(u, reads))
                        pending.remove(url)
                        batch.append(url)
                        group = section(url, scope.url)
                        reads[group] = reads.get(group, 0) + 1
                    if not batch:
                        break
                    responses = await asyncio.gather(*(read_page(u) for u in batch), return_exceptions=True)
                    prefetched = dict(zip(batch, responses))
                current = next(iter(prefetched))
                fetched = prefetched.pop(current)
                queue.remove(current)
                if current in visited:
                    continue
                visited.add(current)
                group = section(current, scope.url)
                section_reads[group] = section_reads.get(group, 0) + 1
                result.attempted += 1
                await report("Reading the next page…", current)
                try:
                    if isinstance(fetched, BaseException):
                        raise fetched
                    cached, page_response = fetched
                    if page_response is None:
                        result.trace.append(
                            {"url": current, "status": "robots-disallowed", "cache": "not-used", "bytes": 0}
                        )
                        result.observations.append(Observation(current, "unavailable"))
                        result.warnings.append({"url": current, "reason": "Disallowed by robots.txt"})
                        continue
                    response = page_response
                    result.trace.append(
                        {
                            "url": current,
                            "status": response.status,
                            "cache": "revalidated" if response.status == 304 and cached else "downloaded",
                            "bytes": len(response.body),
                        }
                    )
                    if response.status in {404, 410}:
                        if cache:
                            await asyncio.to_thread(cache.delete, current)
                        result.observations.append(Observation(current, "not-found"))
                        continue
                    source: Source | None
                    if response.status == 304 and cached:
                        source, links = Source.model_validate(cached["source"]), cached["links"]
                        result.cache_hits += 1
                        response.headers = {
                            "etag": cached["etag"],
                            "last-modified": cached["last_modified"],
                            **response.headers,
                        }
                    else:
                        if response.status != 200:
                            raise FetchError(f"HTTP {response.status}")
                        if response.content_type.split(";", 1)[0].lower() not in {"text/html", "application/xhtml+xml"}:
                            raise FetchError("Unsupported content type")
                        source, links = await asyncio.to_thread(extract_page, response.body, response.url)
                    for link in links:
                        enqueue(link)
                    if not source:
                        raise FetchError("No usable main content; page may require JavaScript")
                    # Preserve the requested URL as identity so redirects cannot orphan known pages.
                    # The final destination has already passed the same scope and robots checks.
                    if response.url != current:
                        source = source.model_copy(update={"url": current, "id": source_id(current)})
                        visited.add(response.url)
                    if cache:
                        result.trace[-1]["storage"] = await asyncio.to_thread(
                            cache.put, current, source, links, response.headers
                        )
                    source_size = len(source.content) + len(source.title) + len(source.description)
                    if text_size + source_size > text_budget:
                        result.stop_reason = "text_budget"
                        result.truncated = True
                        result.observations.append(Observation(current, "unavailable"))
                        break
                    text_size += source_size
                    result.sources.append(source)
                    await report(
                        f"{'Reused unchanged page' if response.status == 304 else 'Read'}: {source.title[:150]}",
                        current,
                    )
                    result.observations.append(
                        Observation(current, "ok", content_hash(source.title, source.description, source.content))
                    )
                except (ValueError, OSError) as error:
                    result.trace.append({"url": current, "status": "unavailable", "cache": "not-used", "bytes": 0})
                    result.observations.append(Observation(current, "unavailable"))
                    warning = {"url": current, "reason": str(error)[:200]}
                    if isinstance(error, BlockedRedirect):
                        warning["redirect_url"] = error.destination
                    result.warnings.append(warning)
                    await report("Skipping a page without usable content; continuing with the rest.", current)
                current = None
            if selected is not None and not queue and result.stop_reason == "exhausted":
                result.stop_reason = "coverage_plan_finished"
            result.truncated = result.truncated or bool(queue) or bool(sitemaps)
    except (TimeoutError, FetchError, DownloadBudget) as error:
        result.truncated = True
        result.stop_reason = (
            "time_budget"
            if isinstance(error, TimeoutError)
            else "download_budget"
            if isinstance(error, DownloadBudget)
            else "fetch_failure"
        )
        result.warnings.append(
            {
                "url": current or scope.url,
                "reason": "Crawl deadline exceeded" if isinstance(error, TimeoutError) else str(error),
            }
        )
        if current and not any(o.url == current for o in result.observations):
            result.observations.append(Observation(current, "unavailable"))
    result.discovery_state = {
        "urls": sorted(queued - visited - previous - {scope.url}),
        "sitemaps": {u: sitemap_offsets.get(u, 0) for u in sitemaps},
    }
    result.duration_ms = round((time.monotonic() - started_at) * 1000)
    result.unread = len(queued - visited)
    result.truncated = result.truncated or bool(result.unread)
    result.discovered = len(queued)
    return result
