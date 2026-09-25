from __future__ import annotations

import asyncio
import inspect
import socket
from collections.abc import AsyncIterator
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, cast

import aiohttp
import pytest
from pytest import MonkeyPatch

from brief.crawl.extract import extract_page
from brief.crawl.fetch import (
    BlockedRedirect,
    FetchError,
    PublicResolver,
    Response,
    SafeFetcher,
    normalize_url,
    public_socket,
)
from brief.crawl.runner import Scope, crawl

if TYPE_CHECKING:
    from brief.interfaces import URLPolicy


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "name,phrase", [("docs", "Authorization"), ("agency", "discovery workshop"), ("shop", "seven days")]
)
def test_extraction_preserves_useful_content_and_metadata(name: str, phrase: str) -> None:
    source, links = extract_page((FIXTURES / f"{name}.html").read_bytes(), "https://example.com/")
    assert source is not None
    assert source.title and source.description
    assert phrase in source.content
    assert "FOOTER_NOISE" not in source.content
    assert "SECRET_SCRIPT_TEXT" not in source.content
    assert links
    assert all("utm_source" not in link for link in links)


def test_empty_javascript_shell_is_not_evidence() -> None:
    source, _ = extract_page(
        b'<html><head><title>App</title></head><body><div id="root"></div><script>renderApp()</script></body></html>',
        "https://example.com/",
    )
    assert source is None


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1",
        "http://[::1]",
        "http://[::ffff:127.0.0.1]",
        "http://localhost",
        "http://db.internal",
        "file:///etc/passwd",
        "https://user:password@example.com",
        "https://example.com:8443",
        "https://example.com\\@127.0.0.1/",
        "https://example.com/\nfoo",
        "http://2130706433",
    ],
)
def test_reject_unsafe_urls(url: str) -> None:
    with pytest.raises(FetchError):
        normalize_url(url)


def test_url_canonicalization_and_scope() -> None:
    assert (
        normalize_url("https://EXAMPLE.com:443/docs?utm_source=x&lang=en#start") == "https://example.com/docs?lang=en"
    )
    scope = Scope("https://example.com/docs/")
    assert scope.contains("https://example.com/docs/api")
    assert not scope.contains("https://example.com/docs-other")
    assert not scope.contains("https://example.com/docs/%2e%2e/private")
    assert not scope.contains("https://other.com/docs")
    versioned = Scope("https://example.com/docs/v1.0/")
    assert versioned.contains("https://example.com/docs/v1.0/api")
    assert not versioned.contains("https://example.com/docs/v2.0/api")


async def test_dns_and_actual_socket_reject_private_addresses(monkeypatch: MonkeyPatch) -> None:
    async def addresses(*args: Any, **kwargs: Any) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", addresses)
    with pytest.raises(OSError, match="private"):
        await PublicResolver().resolve("public-looking.example.com", 443)
    with pytest.raises(OSError, match="blocked"):
        public_socket((socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("10.0.0.1", 443)))


class FakeFetcher:
    interval = 0.0

    def __init__(self, pages: dict[str, Response]) -> None:
        self.pages = pages
        self.visited: list[str] = []

    async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
        verdict = allowed(url)
        assert await verdict if inspect.isawaitable(verdict) else verdict, url
        self.visited.append(url)
        response = self.pages.get(url, Response(url, 404, "text/plain", b""))
        if isinstance(response, Exception):
            raise response
        return response


def page(url: str, fixture: str = "docs") -> Response:
    return Response(url, 200, "text/html; charset=utf-8", (FIXTURES / f"{fixture}.html").read_bytes())


async def test_crawl_respects_robots_and_sitemap_and_reports_coverage() -> None:
    root = "https://example.com/"
    fetcher = FakeFetcher(
        {
            root + "robots.txt": Response(root + "robots.txt", 200, "text/plain", b"User-agent: *\nDisallow: /login\n"),
            root + "sitemap.xml": Response(
                root + "sitemap.xml",
                200,
                "application/xml",
                b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/services</loc></url><url><loc>https://evil.test/external</loc></url></urlset>',
            ),
            root: page(root),
            root + "services": page(root + "services", "agency"),
        }
    )
    result = await crawl(root, fetcher=fetcher)
    assert len(result.sources) == 2
    assert root + "services" in fetcher.visited
    assert root + "login" not in fetcher.visited
    assert not any("evil.test" in url for url in fetcher.visited)
    assert any("robots" in w["reason"] for w in result.warnings)


async def test_known_pages_have_priority_over_new_discovery_and_budget_is_explicit() -> None:
    root = "https://example.com/"
    fetcher = FakeFetcher({root: page(root), root + "known": page(root + "known", "shop")})
    result = await crawl(root, [root + "known"], max_pages=2, fetcher=fetcher)
    assert [s.url for s in result.sources] == [root, root + "known"]
    assert result.truncated
    assert result.attempted == 2


async def test_not_found_is_distinct_from_transient_failure() -> None:
    root = "https://example.com/"
    fetcher = FakeFetcher({root: page(root), root + "broken": Response(root + "broken", 503, "text/plain", b"down")})
    result = await crawl(root, [root + "missing", root + "broken"], max_pages=3, fetcher=fetcher)
    outcomes = {o.url: o.outcome for o in result.observations}
    assert outcomes[root + "missing"] == "not-found"
    assert outcomes[root + "broken"] == "unavailable"


async def test_robots_failure_defers_crawl() -> None:
    root = "https://example.com/"
    fetcher = FakeFetcher(
        {root: page(root), root + "robots.txt": Response(root + "robots.txt", 503, "text/plain", b"")}
    )
    result = await crawl(root, fetcher=fetcher)
    assert not result.sources
    assert root not in fetcher.visited
    assert "robots.txt unavailable" in result.warnings[0]["reason"]


async def test_deadline_reports_partial_progress() -> None:
    class Slow(FakeFetcher):
        async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
            await asyncio.sleep(0.1)
            return await super().get(url, allowed=allowed)

    result = await crawl("https://example.com/", fetcher=Slow({}), deadline=0.01)
    assert result.truncated
    assert "deadline" in result.warnings[0]["reason"]


@pytest.mark.parametrize("destination", ["http://169.254.169.254/", "https://docs.example.org/latest/"])
async def test_redirect_is_revalidated_before_second_request(destination: str) -> None:
    class Redirect:
        status = 302

        def __init__(self) -> None:
            self.headers = {"Location": destination}

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

    class Session:
        calls = 0

        def get(self, *args: Any, **kwargs: Any) -> Redirect:
            self.calls += 1
            assert kwargs["allow_redirects"] is False
            return Redirect()

    fetcher = SafeFetcher(interval=0)
    session = Session()
    fetcher.session = cast(aiohttp.ClientSession, session)
    with pytest.raises(FetchError) as error:
        await fetcher.get("https://example.com/", allowed=lambda url: url == "https://example.com/")
    if destination.startswith("https://"):
        assert isinstance(error.value, BlockedRedirect)
        assert error.value.destination == destination
    else:
        assert not isinstance(error.value, BlockedRedirect)
    assert session.calls == 1


def test_catalog_retains_names_and_unicode_metadata() -> None:
    source, links = extract_page((FIXTURES / "catalog.html").read_bytes(), "https://example.com/")
    assert source is not None
    assert "A Light in the Attic" in source.content
    assert "Tipping the Velvet" in source.content
    assert source.title == "Library — Books"
    assert "— browse" in source.description
    assert links[0] == "https://example.com/light"


async def test_secondary_origin_uses_its_own_robots_policy() -> None:
    root = "https://example.com/"
    body = (FIXTURES / "agency.html").read_bytes().replace(b"/work", b"https://www.example.com/work")
    fetcher = FakeFetcher(
        {
            root: Response(root, 200, "text/html", body),
            "https://www.example.com/robots.txt": Response(
                "https://www.example.com/robots.txt", 200, "text/plain", b"User-agent: *\nDisallow: /work\n"
            ),
            "https://www.example.com/work": page("https://www.example.com/work"),
        }
    )
    result = await crawl(root, fetcher=fetcher)
    assert len(result.sources) == 1
    assert "https://www.example.com/robots.txt" in fetcher.visited
    assert "https://www.example.com/work" not in fetcher.visited


async def test_sitemap_entities_are_rejected_without_stopping_page_crawl() -> None:
    root = "https://example.com/"
    fetcher = FakeFetcher(
        {
            root: page(root),
            root + "sitemap.xml": Response(
                root + "sitemap.xml",
                200,
                "application/xml",
                b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><urlset><loc>&xxe;</loc></urlset>',
            ),
        }
    )
    result = await crawl(root, max_pages=1, fetcher=fetcher)
    assert len(result.sources) == 1
    assert any("Sitemap unavailable" in warning["reason"] for warning in result.warnings)


async def test_oversized_response_is_rejected_during_streaming() -> None:
    class Content:
        async def iter_chunked(self, _: int) -> AsyncIterator[bytes]:
            yield b"1234567890"
            yield b"1234567890"
            raise AssertionError("Must stop reading when the byte limit is exceeded")

    class LargeResponse:
        status = 200

        def __init__(self) -> None:
            self.headers = {"Content-Type": "text/html"}
            self.content = Content()

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

    class Session:
        def get(self, *args: Any, **kwargs: Any) -> LargeResponse:
            return LargeResponse()

    fetcher = SafeFetcher(interval=0, max_bytes=15)
    session = Session()
    fetcher.session = cast(aiohttp.ClientSession, session)
    with pytest.raises(FetchError, match="byte limit"):
        await fetcher.get("https://example.com/", allowed=lambda url: True)


async def test_scope_sitemap_ranking_and_filter_before_url_budget() -> None:
    root = "https://example.com/"
    docs = root + "docs/"
    index = (
        "<sitemapindex>"
        + "".join(
            f"<sitemap><loc>{root}{path}/sitemap.xml</loc></sitemap>"
            for path in ["blog", "fr/blog", "products", "docs"]
        )
        + "</sitemapindex>"
    )
    # Relevant pages occur beyond the old 1,000-entry slice.
    leaf = (
        "<urlset>"
        + "".join(f"<url><loc>{root}blog/{i}</loc></url>" for i in range(1100))
        + f"<url><loc>{docs}api</loc></url></urlset>"
    )

    class DiscoveryFetcher:
        interval = 0.0

        def __init__(self) -> None:
            self.seen: list[str] = []

        async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
            self.seen.append(url)
            if url == root + "robots.txt":
                return Response(url, 200, "text/plain", f"Sitemap: {root}sitemap.xml".encode())
            if url == root + "sitemap.xml":
                return Response(url, 200, "application/xml", index.encode())
            if url == docs + "sitemap.xml":
                return Response(url, 200, "application/xml", leaf.encode())
            return Response(url, 404, "text/plain", b"")

    fetcher = DiscoveryFetcher()
    result = await crawl(docs, fetcher=fetcher)
    assert fetcher.seen[2] == docs + "sitemap.xml"
    assert docs + "api" in fetcher.seen
    assert not any("/blog/0" in u for u in fetcher.seen)
    assert result.sitemap_discovery is not None
    assert result.sitemap_discovery["fetches"] == 5


async def test_sitemap_cycles_external_and_unsafe_locations_do_not_fetch() -> None:
    root = "https://example.com/"

    class IndexFetcher:
        interval = 0.0

        def __init__(self) -> None:
            self.seen: list[str] = []

        async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
            self.seen.append(url)
            if url.endswith("robots.txt"):
                return Response(url, 404, "text/plain", b"")
            if url.endswith("sitemap.xml"):
                return Response(
                    url,
                    200,
                    "application/xml",
                    b"<sitemapindex><sitemap><loc>https://example.com/sitemap.xml</loc></sitemap><sitemap><loc>http://127.0.0.1/secret</loc></sitemap><sitemap><loc>https://other.example.com/sitemap.xml</loc></sitemap></sitemapindex>",
                )
            return Response(url, 404, "text/plain", b"")

    fetcher = IndexFetcher()
    result = await crawl(root, fetcher=fetcher)
    assert result.sitemap_discovery is not None
    assert result.sitemap_discovery["fetches"] == 1
    assert len(fetcher.seen) == 3


async def test_sitemap_byte_budget_still_allows_page_reading() -> None:
    root = "https://example.com/"
    index = (
        "<sitemapindex>" + "".join(f"<sitemap><loc>{root}{i}.xml</loc></sitemap>" for i in range(5)) + "</sitemapindex>"
    )
    body = b"<urlset>" + b" " * 1_999_980 + b"</urlset>"

    class BudgetFetcher:
        interval = 0.0

        def __init__(self) -> None:
            self.seen: list[str] = []

        async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
            self.seen.append(url)
            if url.endswith("robots.txt"):
                return Response(url, 404, "text/plain", b"")
            if url.endswith("sitemap.xml"):
                return Response(url, 200, "application/xml", index.encode())
            if url.endswith(".xml"):
                return Response(url, 200, "application/xml", body)
            return Response(url, 404, "text/plain", b"")

    fetcher = BudgetFetcher()
    result = await crawl(root, fetcher=fetcher)
    assert result.sitemap_discovery is not None
    assert result.sitemap_discovery["stop_reason"] == "byte_budget"
    assert result.sitemap_discovery["fetches"] == 3
    assert root in fetcher.seen
    assert root + "2.xml" not in fetcher.seen


@pytest.mark.parametrize("page_budget", [2, 4, 5])
async def test_parallel_reads_overlap_without_exceeding_page_budget(page_budget: int) -> None:
    root = "https://example.com/"

    class Concurrent(FakeFetcher):
        active = 0
        peak = 0

        async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
            if url in self.pages:
                self.active += 1
                self.peak = max(self.peak, self.active)
                try:
                    await asyncio.sleep(0.02 if url == root else 0.005)
                    return await super().get(url, allowed=allowed)
                finally:
                    self.active -= 1
            return await super().get(url, allowed=allowed)

    urls = [root, *(root + f"known-{i}" for i in range(5))]
    fetcher = Concurrent({url: page(url) for url in urls})
    result = await crawl(root, urls[1:], fetcher=fetcher, max_pages=page_budget)
    assert fetcher.peak == min(4, page_budget)
    assert fetcher.active == 0
    assert [s.url for s in result.sources] == urls[:page_budget]
    assert urls[page_budget] not in fetcher.visited
    assert result.attempted == page_budget
    assert result.truncated


async def test_deadline_cancels_all_parallel_reads() -> None:
    root = "https://example.com/"

    class Blocked(FakeFetcher):
        started = 0
        stopped = 0

        async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
            if url in {root, root + "a", root + "b", root + "c"}:
                self.started += 1
                try:
                    await asyncio.Event().wait()
                finally:
                    self.stopped += 1
            return await super().get(url, allowed=allowed)

    fetcher = Blocked({})
    result = await crawl(root, [root + "a", root + "b", root + "c"], fetcher=fetcher, deadline=0.05)
    assert fetcher.started == fetcher.stopped == 4
    assert result.stop_reason == "time_budget"
    assert result.unread == 4


async def test_parallel_transport_preserves_spacing() -> None:
    starts = []
    loop = asyncio.get_running_loop()

    class Content:
        async def iter_chunked(self, _: int) -> AsyncIterator[bytes]:
            yield b"ok"

    class Reply:
        status = 200
        content = Content()

        def __init__(self) -> None:
            self.headers = {"Content-Type": "text/html"}

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

    class Session:
        def get(self, *args: Any, **kwargs: Any) -> Reply:
            starts.append(loop.time())
            return Reply()

    fetcher = SafeFetcher(interval=0.03)
    session = Session()
    fetcher.session = cast(aiohttp.ClientSession, session)
    # All callers arrive while the previous request's delay is still active.
    fetcher.last_request = loop.time()
    await asyncio.gather(*(fetcher.get(f"https://example.com/{i}", allowed=lambda url: True) for i in range(3)))
    assert len(starts) == 3
    assert all(b - a >= 0.025 for a, b in pairwise(starts))
