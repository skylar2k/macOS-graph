from urllib.parse import quote


def profile_guid(profile_id: str) -> str:
    """The bare profile GUID from an enrollment profile id.

    Graph returns composite ids like `ECV2_<token part>_<profile GUID>`, but the
    profile endpoints want only the last segment. Bare GUIDs pass through unchanged.
    """
    return profile_id.rsplit("_", 1)[-1]


def token_id_from_profile_id(profile_id: str) -> str | None:
    """The ADE token id embedded in an `ECV2_<token id>_<profile GUID>` profile id.

    None for ids without a token part (a bare GUID, or legacy profile ids).
    """
    parts = profile_id.split("_")
    return parts[1] if len(parts) >= 3 else None


def quote_id(value: str) -> str:
    """Percent-encode an id for use as a single URL path segment."""
    return quote(value, safe="")
