from urllib.parse import quote

from ..errors import GraphMacosError


def dep_profile_split_guid(profile_id: str) -> str:
    """The bare profile GUID from an enrollment profile id.

    Graph returns composite ids like `ECV2_<token part>_<profile GUID>`, but the
    profile endpoints want only the last segment. Bare GUIDs pass through unchanged.
    """
    return profile_id.rsplit("_", 1)[-1]


def token_id_from_dep_profile_id(profile_id: str) -> str | None:
    """The ADE token id embedded in an `ECV2_<token id>_<profile GUID>` profile id.

    None for ids without a token part (a bare GUID, or legacy profile ids).
    """
    parts = profile_id.split("_")
    return parts[1] if len(parts) >= 3 else None


def quote_id(value: str) -> str:
    """Percent-encode an id for use as a single URL path segment."""
    return quote(value, safe="")


def resolve_token_id(profile_id: str, token_id: str | None = None) -> str:
    """The ADE token id for a profile: --token if given, else the one embedded in the id.

    Raises GraphMacosError if neither is available or the two disagree.
    """
    embedded = token_id_from_dep_profile_id(profile_id)
    if token_id and embedded and token_id != embedded:
        raise GraphMacosError(
            f"token {token_id} does not match the token in the profile id ({embedded})"
        )
    if not (resolved := token_id or embedded):
        raise GraphMacosError("a token id is required unless the profile id is a full ECV2_… id")
    return resolved
