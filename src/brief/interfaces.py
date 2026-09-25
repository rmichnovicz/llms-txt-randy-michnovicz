"""Structural interfaces for injected model and HTTP adapters.

Database rows and schema-validated JSON payloads remain heterogeneous dictionaries;
callbacks and service boundaries describe the operations callers actually require.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from brief.contracts import GenerationInput
    from brief.crawl.fetch import Response
    from brief.model import Completion


URLPolicy = Callable[[str], bool | Awaitable[bool]]
Progress = Callable[[dict[str, Any]], Awaitable[None]]


class Fetcher(Protocol):
    interval: float

    async def get(self, url: str, *, allowed: URLPolicy, headers: dict[str, str] | None = None) -> Response: ...


@runtime_checkable
class Completer(Protocol):
    def complete(self, request: dict[str, Any], *, result_type: type[BaseModel] = ...) -> Completion: ...


class Generator(Protocol):
    def generate(self, context: GenerationInput) -> Completion: ...


class ResponseEndpoint(Protocol):
    @property
    def create(self) -> Callable[..., Any]: ...


class ModelClient(Protocol):
    @property
    def responses(self) -> ResponseEndpoint: ...


class PageReader(Protocol):
    def get(self, url: str) -> dict[str, Any]: ...


class Disconnectable(Protocol):
    async def is_disconnected(self) -> bool: ...
