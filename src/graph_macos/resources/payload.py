"""Build request bodies from --set / --patch / --patch-file."""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..errors import GraphMacosError


def parse_set(items: Iterable[str]) -> dict[str, Any]:
    """Turn KEY=VALUE items into a dict. VALUE is parsed as JSON when it is valid JSON
    (true, 3, ["a"], {"x": 1}), otherwise kept as a string."""
    out: dict[str, Any] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise GraphMacosError(f"--set expects KEY=VALUE, got {item!r}")
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


def build_body(
    set_items: Iterable[str] = (),
    patch_json: str | None = None,
    patch_file: str | None = None,
    odata_type: str | None = None,
) -> dict[str, Any]:
    """Merge --patch-file, --patch and --set (later sources win) into one request body.

    Raises if no source gave anything.
    """
    body: dict[str, Any] = {}
    for label, raw in (
        ("--patch-file", Path(patch_file).read_text() if patch_file else None),
        ("--patch", patch_json),
    ):
        if raw is None:
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as e:
            raise GraphMacosError(f"{label} is not valid JSON: {e}") from e
        if not isinstance(value, dict):
            raise GraphMacosError(f"{label} must be a JSON object")
        body.update(value)
    body.update(parse_set(set_items))
    if not body:
        raise GraphMacosError("nothing to send: give --set, --patch or --patch-file")
    if odata_type:
        body.setdefault("@odata.type", odata_type)
    return body
