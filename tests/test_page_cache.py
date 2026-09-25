from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from test_crawl import FakeFetcher, page
from test_store import source

from brief.crawl.cache import PageCache
from brief.crawl.fetch import Response
from brief.crawl.runner import crawl

if TYPE_CHECKING:
    from brief.interfaces import URLPolicy
    from brief.store import Store


pytestmark = pytest.mark.integration
ROOT = "https://example.com/"


class ValidatingFetcher(FakeFetcher):
    def __init__(self, status: int = 200) -> None:
        super().__init__({ROOT: page(ROOT)})
        self.status = status
        self.validators: list[dict[str, str] | None] = []

    async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
        self.validators.append(headers)
        response = await super().get(url, allowed=allowed)
        if url == ROOT:
            if self.status == 304:
                return Response(url, 304, "", b"", {"etag": '"one"'})
            response.headers = {"etag": '"one"', "cache-control": "public, max-age=0"}
        return response


async def test_conditional_reuse_and_site_isolation(store: Store) -> None:
    project, _, _ = store.create_project(ROOT)
    cache = PageCache(store.db, project["site_id"])
    first = await crawl(ROOT, fetcher=ValidatingFetcher(), cache=cache, max_pages=1)
    transport = ValidatingFetcher(304)
    second = await crawl(ROOT, fetcher=transport, cache=cache, max_pages=1)
    assert second.sources == first.sources
    assert second.cache_hits == 1 and second.conditional_requests == 1
    assert {"If-None-Match": '"one"'} in transport.validators
    assert second.trace[0]["cache"] == "revalidated"
    other, _, _ = store.create_project(ROOT)
    assert PageCache(store.db, other["site_id"]).get(ROOT) is None


@pytest.mark.parametrize(
    "headers", [{"cache-control": "no-store"}, {"cache-control": "private"}, {"vary": "Cookie"}, {"vary": "*"}]
)
def test_cache_respects_storage_restrictions(store: Store, headers: dict[str, str]) -> None:
    project, _, _ = store.create_project(ROOT)
    cache = PageCache(store.db, project["site_id"])
    cache.put(ROOT, source(), [], {"etag": '"one"'})
    assert cache.get(ROOT)
    assert headers is not None
    cache.put(ROOT, source(), [], headers)
    assert cache.get(ROOT) is None


def test_extraction_version_invalidates_old_cache(store: Store) -> None:
    project, _, _ = store.create_project(ROOT)
    cache = PageCache(store.db, project["site_id"])
    cache.put(ROOT, source(), [], {})
    with store.db.connect() as c:
        c.execute("UPDATE page_cache SET extraction_version='old'")
    assert cache.get(ROOT) is None


async def test_cached_page_cannot_bypass_new_robots_rules(store: Store) -> None:
    project, _, _ = store.create_project(ROOT)
    cache = PageCache(store.db, project["site_id"])
    await crawl(ROOT, fetcher=ValidatingFetcher(), cache=cache, max_pages=1)
    transport = FakeFetcher(
        {ROOT + "robots.txt": Response(ROOT + "robots.txt", 200, "text/plain", b"User-agent: *\nDisallow: /\n")}
    )
    result = await crawl(ROOT, fetcher=transport, cache=cache)
    assert not result.sources and result.cache_hits == 0
    assert ROOT not in transport.visited
    assert result.trace[0]["status"] == "robots-disallowed"


async def test_removed_page_evicts_cache_and_records_not_found(store: Store) -> None:
    project, _, _ = store.create_project(ROOT)
    cache = PageCache(store.db, project["site_id"])
    cache.put(ROOT, source(), [], {})
    result = await crawl(ROOT, fetcher=FakeFetcher({}), cache=cache, max_pages=1)
    assert not result.sources
    assert cache.get(ROOT) is None
    assert result.observations[0].outcome == "not-found"
