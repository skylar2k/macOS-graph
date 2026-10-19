"""Graph transport layer.

msal and requests are slow to import, so everything that needs them is a lazy import
(PEP 810): `gmac --help` and the resource specs never load them.
"""

lazy from .api import API_VERSION, GraphClient, batch_error
lazy from .auth import AuthError, GraphAuth
lazy from .client import Graph, GraphError

__all__ = [
    "API_VERSION",
    "AuthError",
    "Graph",
    "GraphAuth",
    "GraphClient",
    "GraphError",
    "batch_error",
]
