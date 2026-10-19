"""The seam between commands and the network: tests replace `make_graph` with a fake."""

from collections.abc import Sequence

from ..graph.api import API_VERSION
lazy from ..graph.client import Graph  # msal and requests load on first use


def make_graph(scopes: Sequence[str], api: API_VERSION = API_VERSION.V1) -> Graph:
    return Graph(scopes=list(scopes), api_ver=api)
