import pytest

from graph_macos.cli import runtime
from tests.fakes import FakeGraph


@pytest.fixture
def fake_graph(monkeypatch):
    """Patch the CLI's Graph factory; returns a function to install a FakeGraph."""
    made = []

    def install(**kw):
        g = FakeGraph(**kw)
        made.append(g)
        monkeypatch.setattr(
            runtime, "make_graph", lambda scopes, api=None: setattr(g, "scopes", tuple(scopes)) or g
        )
        return g

    return install
