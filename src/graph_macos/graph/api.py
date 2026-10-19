"""Dependency-free pieces of the Graph layer, importable without msal or requests."""

from collections.abc import Iterable, Iterator
from enum import StrEnum
from typing import Any, Protocol


class API_VERSION(StrEnum):
    V1 = "v1.0"
    BETA = "beta"


class GraphClient(Protocol):
    """The part of `Graph` that resource operations use.

    Operations are typed against this, not the concrete class, so they run against
    test fakes (and any alternative transport) without importing msal or requests.
    """

    def get(self, url: str, /, **kw: Any) -> dict: ...

    def paged(self, url: str, /, **kw: Any) -> Iterator[dict]: ...

    def batch(self, requests_: Iterable[dict], /) -> Iterator[dict]: ...

    def request(self, method: str, url: str, /, **kw: Any) -> Any: ...


def error_message(body: Any, default: str) -> str:
    """Graph's own error message from a response body, else `default`."""
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        return body["error"].get("message") or default
    return default


def batch_error(resp: dict) -> str:
    """Human-readable message for a failed /$batch sub-response."""
    return error_message(resp.get("body"), str(resp["status"]))
