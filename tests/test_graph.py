from unittest import mock

import pytest
import requests

from graph_macos.graph.client import Graph, GraphError, _retry_delay, batch_error


class FakeAuth:
    def get_token(self, scopes):
        return "token"


class Resp:
    def __init__(self, status, headers=None, body=None):
        self.status_code = status
        self.headers = headers or {}
        self.ok = status < 400
        self.reason = "reason"
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError
        return self._body


def graph_with(*outcomes):
    g = Graph(["scope"], auth=FakeAuth())
    it = iter(outcomes)

    def fake(*a, **kw):
        v = next(it)
        if isinstance(v, Exception):
            raise v
        return v

    g.session.request = fake
    return g


@pytest.fixture(autouse=True)
def no_sleep():
    with mock.patch("time.sleep") as s:
        yield s


def test_retries_throttling_and_honours_retry_after(no_sleep):
    g = graph_with(Resp(429, {"Retry-After": "3"}), Resp(503), Resp(200, body={"ok": 1}))
    assert g.get("/a") == {"ok": 1}
    assert no_sleep.call_args_list[0] == mock.call(3.0)
    assert len(no_sleep.call_args_list) == 2


def test_idempotent_methods_retry_connection_errors():
    g = graph_with(requests.ConnectionError(), Resp(200, body={}))
    assert g.request("DELETE", "/a").status_code == 200


def test_post_does_not_retry_connection_errors():
    g = graph_with(requests.ConnectionError())
    with pytest.raises(requests.ConnectionError):
        g.request("POST", "/a")


def test_error_carries_graph_message():
    g = graph_with(Resp(403, body={"error": {"message": "Insufficient privileges"}}))
    with pytest.raises(GraphError, match="403 Insufficient privileges") as e:
        g.get("/a")
    assert e.value.status == 403


def test_retries_exhausted_raises():
    g = graph_with(*[Resp(429)] * 6)
    with pytest.raises(GraphError) as e:
        g.get("/a")
    assert e.value.status == 429


def test_retry_after_is_capped_and_http_date_tolerated():
    assert _retry_delay("9999", 0) == 120.0
    assert _retry_delay("Wed, 21 Oct 2015 07:28:00 GMT", 0) <= 2


def test_batch_chunks_orders_and_retries_throttled_items():
    calls = []

    def post(url, json):
        calls.append(len(json["requests"]))
        out = [
            {"id": r["id"], "status": 429 if r["id"] == "3" and len(calls) == 1 else 204}
            for r in json["requests"]
        ]
        return {"responses": out[::-1]}  # Graph may answer out of order

    g = Graph(["scope"], auth=FakeAuth())
    g.post = post  # type: ignore[method-assign]
    res = list(g.batch({"method": "DELETE", "url": f"/x/{i}"} for i in range(45)))
    assert calls == [20, 1, 20, 5]
    assert [r["id"] for r in res[:3]] == ["0", "1", "2"]
    assert len(res) == 45 and {r["status"] for r in res} == {204}


def test_batch_error_message():
    assert batch_error({"status": 404, "body": {"error": {"message": "gone"}}}) == "gone"
    assert batch_error({"status": 500}) == "500"
