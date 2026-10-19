from ..graph.api import API_VERSION
from .base import Resource

USERS = Resource(
    path=("users",),
    collection="/users",
    help="Entra ID users.",
    read_scopes=("User.Read.All",),
    api=API_VERSION.V1,
    supports_search=True,
    default_select="id,userPrincipalName,displayName,accountEnabled",
)

GROUPS = Resource(
    path=("groups",),
    collection="/groups",
    help="Entra ID groups.",
    read_scopes=("Group.Read.All",),
    api=API_VERSION.V1,
    supports_search=True,
    default_select="id,displayName,description,groupTypes,securityEnabled",
)

RESOURCES = (USERS, GROUPS)
