"""Test doubles shared across the suite."""


class FakeGraph:
    """Stands in for Graph: records calls, serves canned pages and batch responses."""

    def __init__(self, pages=None, batch_status=204, batch_body=None, get_result=None):
        self.pages = pages or {}
        self.batch_status = batch_status
        self.batch_body = batch_body
        self.get_result = get_result or {}
        self.paged_calls = []
        self.paged_kw = []
        self.get_calls = []
        self.batch_calls = []
        self.request_calls = []

    def paged(self, url, **kw):
        self.paged_calls.append((url, kw.get("params")))
        self.paged_kw.append(kw)
        yield from self.pages.get(url, [])

    def get(self, url, **kw):
        self.get_calls.append(url)
        return dict(self.get_result)

    def batch(self, requests_):
        reqs = list(requests_)
        self.batch_calls.append(reqs)
        for n, _ in enumerate(reqs):
            resp = {"id": str(n), "status": self.batch_status}
            if self.batch_status >= 400:
                resp["body"] = {"error": {"message": "nope"}}
            elif self.batch_body is not None:
                resp["body"] = self.batch_body(n)
            yield resp

    def request(self, method, url, **kw):
        self.request_calls.append((method, url, kw.get("json")))
