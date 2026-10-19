import itertools
import random
import time
from collections.abc import Iterable, Iterator
from email.utils import parsedate_to_datetime
from typing import Any, Protocol

import requests

from ..errors import GraphMacosError
from .api import API_VERSION, error_message
from .auth import GraphAuth

BATCH_LIMIT = 20  # Graph's maximum sub-requests per /$batch call
MAX_ATTEMPTS = 6
MAX_WAIT = 120.0  # seconds; caps both backoff and server-supplied Retry-After
RETRY_STATUS = frozenset({429, 502, 503, 504})
IDEMPOTENT = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})


class GraphError(GraphMacosError):
    """A non-retryable (or retries exhausted) Graph failure, with Graph's own message."""

    def __init__(self, status: int, message: str, url: str = ""):
        super().__init__(f"{status} {message}" + (f" ({url})" if url else ""))
        self.status = status


def _retry_delay(retry_after: str | None, attempt: int) -> float:
    """Honour Retry-After (seconds or HTTP-date), else exponential backoff with full jitter."""
    if retry_after:
        try:
            delay = float(retry_after)
        except ValueError:
            try:
                delay = parsedate_to_datetime(retry_after).timestamp() - time.time()
            except TypeError, ValueError:
                delay = 0.0
        if delay > 0:
            return min(delay, MAX_WAIT)
    return min(random.uniform(0, 2 ** (attempt + 1)), MAX_WAIT)


class TokenProvider(Protocol):
    """Anything that can supply a bearer token for a set of scopes (GraphAuth, or a test fake)."""

    def get_token(self, scopes: list[str]) -> str: ...


class Graph:
    """Thin Graph client. `scopes` is required: each caller asks only for what it needs."""

    def __init__(
        self,
        scopes: list[str],
        auth: TokenProvider | None = None,
        api_ver: API_VERSION = API_VERSION.V1,
    ):
        self.scopes = scopes
        self.auth = auth or GraphAuth()
        self.session = requests.Session()
        self.base = f"https://graph.microsoft.com/{api_ver}"

    def _headers(self) -> dict[str, str]:
        # get_token hits the cache each call, so expired tokens refresh themselves.
        return {"Authorization": f"Bearer {self.auth.get_token(scopes=self.scopes)}"}

    def request(self, method: str, url: str, **kw: Any) -> requests.Response:
        """Send a request, retrying throttling (429), 502/503/504 and, for idempotent
        methods, connection errors and timeouts. Raises GraphError otherwise."""
        if not url.startswith("https"):
            url = self.base + url
        kw.setdefault("timeout", 60)
        extra_headers = kw.pop("headers", None) or {}
        for attempt in range(MAX_ATTEMPTS):
            last = attempt == MAX_ATTEMPTS - 1
            try:
                # Fetched per attempt: a long backoff can outlive the access token.
                r = self.session.request(
                    method, url, headers={**self._headers(), **extra_headers}, **kw
                )
            except requests.ConnectionError, requests.Timeout:
                if method.upper() not in IDEMPOTENT or last:
                    raise
                time.sleep(_retry_delay(None, attempt))
                continue
            if r.status_code in RETRY_STATUS and not last:
                time.sleep(_retry_delay(r.headers.get("Retry-After"), attempt))
                continue
            if not r.ok:
                try:
                    body = r.json()
                except ValueError:
                    body = None
                raise GraphError(r.status_code, error_message(body, r.reason or ""), url)
            return r
        raise AssertionError("unreachable")

    def get(self, url: str, **kw: Any) -> dict:
        return self.request("GET", url, **kw).json()

    def post(self, url: str, **kw: Any) -> dict:
        return self.request("POST", url, **kw).json()

    def batch(self, requests_: Iterable[dict]) -> Iterator[dict]:
        """Send sub-requests via /$batch (20 per call) and yield responses in input order.

        Each item is {"method": ..., "url": "/relative/to/version", "body"?: ...,
        "headers"?: ...}; ids are assigned here. Throttled sub-requests (429/502/503/504)
        are retried individually, honouring their own Retry-After. Each yielded
        response is {"id", "status", "headers", "body"}; a failed sub-request does
        not raise, so check "status"; `batch_error()` extracts the message.
        """
        for chunk in itertools.batched(requests_, BATCH_LIMIT, strict=False):
            pending = {str(i): {**req, "id": str(i)} for i, req in enumerate(chunk)}
            done: dict[str, dict] = {}
            for attempt in range(MAX_ATTEMPTS):
                last = attempt == MAX_ATTEMPTS - 1
                wait = 0.0
                body = self.post("/$batch", json={"requests": list(pending.values())})
                for resp in body["responses"]:
                    if resp["status"] in RETRY_STATUS and not last:
                        retry_after = resp.get("headers", {}).get("Retry-After")
                        wait = max(wait, _retry_delay(retry_after, attempt))
                    else:
                        del pending[resp["id"]]
                        done[resp["id"]] = resp
                if not pending:
                    break
                time.sleep(wait)
            for i in range(len(chunk)):
                yield done[str(i)]

    def paged(self, url: str, **kw: Any) -> Iterator[dict]:
        while url:
            page = self.get(url, **kw)
            yield from page.get("value", [])
            url = page.get("@odata.nextLink", "")
            kw.pop("params", None)  # nextLink already contains the query
