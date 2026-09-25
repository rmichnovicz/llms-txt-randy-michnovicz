from __future__ import annotations

import asyncio
import inspect
import ipaddress
import posixpath
import socket
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiohttp
from aiohttp.abc import AbstractResolver, ResolveResult

if TYPE_CHECKING:
    from brief.interfaces import URLPolicy


USER_AGENT = "BriefBot/0.1"
FETCH_CONCURRENCY = 4


class FetchError(ValueError):
    pass


def public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value.split("%", 1)[0])
    return ip.is_global and not ip.is_multicast and not ip.is_reserved and not getattr(ip, "ipv4_mapped", None)


def normalize_url(value: str) -> str:
    if len(value) > 2048 or "\\" in value or any(ord(c) < 33 for c in value):
        raise FetchError("Invalid URL characters or length")
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise FetchError("Use a public HTTP(S) URL without credentials")
        if parsed.port not in {None, 80 if parsed.scheme == "http" else 443}:
            raise FetchError("Only standard HTTP(S) ports are supported")
        host = parsed.hostname.encode("idna").decode().lower().rstrip(".")
        if "%" in host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise FetchError("Local destinations are not allowed")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if "." not in host:
                raise FetchError("Use a public hostname")
        else:
            if not public_ip(host):
                raise FetchError("Private/reserved destinations are not allowed")
        netloc = f"[{host}]" if ":" in host else host
        path = posixpath.normpath(parsed.path or "/")
        if parsed.path.endswith("/") and not path.endswith("/"):
            path += "/"
        query = [
            (k, v)
            for k, v in parse_qsl(parsed.query, max_num_fields=50)
            if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid"}
        ]
        return urlunsplit((parsed.scheme, netloc, path, urlencode(sorted(query)), ""))
    except (ValueError, UnicodeError) as error:
        raise FetchError(str(error)) from error


class PublicResolver(AbstractResolver):
    """Validate the exact addresses supplied to the connector, not a separate preflight lookup."""

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> list[ResolveResult]:
        addresses = await asyncio.get_running_loop().getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
        if not addresses or any(not public_ip(address[4][0]) for address in addresses):
            raise OSError("DNS resolved to a private/reserved address")
        return [
            {
                "hostname": host,
                "host": address[4][0],
                "port": port,
                "family": address[0],
                "proto": address[2],
                "flags": socket.AI_NUMERICHOST,
            }
            for address in addresses
        ]

    async def close(self) -> None:
        pass


def public_socket(address: tuple[int, int, int, str, Any]) -> socket.socket:
    family, kind, proto, _, sockaddr = address
    if not public_ip(sockaddr[0]):
        raise OSError("Connection to private/reserved address blocked")
    return socket.socket(family=family, type=kind, proto=proto)


@dataclass
class Response:
    url: str
    status: int
    content_type: str
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


class SafeFetcher:
    def __init__(self, *, timeout: int = 12, max_bytes: int = 2_000_000, interval: float = 0.25) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.interval = interval
        self.last_request = 0.0
        self.session: aiohttp.ClientSession | None = None
        self.pacing_lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        connector = aiohttp.TCPConnector(
            resolver=PublicResolver(), socket_factory=public_socket, use_dns_cache=False, limit=FETCH_CONCURRENCY
        )
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,text/plain,application/xml"},
            trust_env=False,
            cookie_jar=aiohttp.DummyCookieJar(),
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self.session is not None:
            await self.session.close()

    async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response:
        from urllib.parse import urljoin

        if self.session is None:
            raise RuntimeError("Use SafeFetcher as an async context manager")
        for _ in range(6):
            url = normalize_url(url)
            verdict = allowed(url)
            if inspect.isawaitable(verdict):
                verdict = await verdict
            if not verdict:
                raise FetchError("URL outside crawl scope or disallowed by robots.txt")
            async with self.pacing_lock:
                await asyncio.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
                self.last_request = time.monotonic()
            try:
                async with self.session.get(url, allow_redirects=False, headers=headers) as response:
                    if response.status in {301, 302, 303, 307, 308}:
                        if not response.headers.get("Location"):
                            raise FetchError("Redirect without destination")
                        url = urljoin(url, response.headers["Location"])
                        headers = None
                        continue
                    content = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        content.extend(chunk)
                        if len(content) > self.max_bytes:
                            raise FetchError("Response exceeds byte limit")
                    return Response(
                        url,
                        response.status,
                        response.headers.get("Content-Type", ""),
                        bytes(content),
                        {
                            k.lower(): v
                            for k, v in response.headers.items()
                            if k.lower() in {"etag", "last-modified", "cache-control", "vary"}
                        },
                    )
            except (aiohttp.ClientError, TimeoutError, OSError) as error:
                # Do not expose resolved internal addresses or arbitrary response bodies.
                raise FetchError(f"Fetch failed ({type(error).__name__})") from error
        raise FetchError("Too many redirects")
