"""Resource specs and the generic operations over them.

A `Resource` describes a Graph collection once (path, scopes, supported verbs, quirks);
the functions here implement list/get/create/update/delete for any spec. Nothing in this
module touches the CLI, so everything is usable (and testable) as a library.
"""

import itertools
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from ..errors import GraphMacosError
from ..graph.api import API_VERSION, GraphClient, batch_error
from ..graph.ids import quote_id

READ_VERBS = frozenset({"list", "get"})
WRITE_VERBS = frozenset({"create", "update", "delete"})
PAGE_SIZE = 999
_PAST_TENSE = {"POST": "created", "PATCH": "updated", "DELETE": "deleted"}


@dataclass(frozen=True)
class Parent:
    """The collection above a sub-resource, e.g. an ADE token for its profiles."""

    name: str  # CLI option name and wording, e.g. "token"
    from_item_id: Callable[[str], str | None] = lambda item_id: None  # noqa: E731
    """Recover the parent id embedded in an item id, if the id format carries it."""
    tag: str | None = None
    """Field to add to listed records holding the parent id (None: don't add one)."""


@dataclass(frozen=True)
class Resource:
    path: tuple[str, ...]  # CLI location: ("devices",) or ("ade", "profiles")
    collection: str  # URL relative to the API version; "{parent}" marks the parent id
    help: str
    read_scopes: tuple[str, ...]
    write_scopes: tuple[str, ...] = ()
    verbs: frozenset[str] = READ_VERBS
    api: API_VERSION = API_VERSION.V1
    id_key: str = "id"
    default_select: str | None = None
    default_filter: str | None = None
    parent: Parent | None = None
    odata_type: str | None = None  # added to create/update bodies when set
    supports_search: bool = False  # Entra directory objects: $search (needs ConsistencyLevel)
    redact: frozenset[str] = frozenset()  # fields never emitted or echoed
    enrich: Callable[[dict], dict] | None = None  # derived fields added to emitted records

    def __post_init__(self) -> None:
        if (self.verbs & WRITE_VERBS) and not self.write_scopes:
            raise ValueError(f"{self.path}: write verbs need write_scopes")
        if unknown := self.verbs - READ_VERBS - WRITE_VERBS:
            raise ValueError(f"{self.path}: unknown verbs {sorted(unknown)}")
        if bool(self.parent) != ("{parent}" in self.collection):
            raise ValueError(f"{self.path}: parent and '{{parent}}' in collection must go together")

    @property
    def noun(self) -> str:
        return self.path[-1]


def combine_filters(*parts: str | None) -> str | None:
    present = [p for p in parts if p]
    if len(present) > 1:
        return " and ".join(f"({p})" for p in present)
    return present[0] if present else None


def _collection_url(res: Resource, parent_id: str | None) -> str:
    if not res.parent:
        return res.collection
    if not parent_id:
        raise GraphMacosError(f"a {res.parent.name} id is required")
    return res.collection.replace("{parent}", quote_id(parent_id))


def resolve_parent(res: Resource, item_id: str, parent_id: str | None) -> str | None:
    """The parent id for an item: the explicit one, else the one embedded in the item id."""
    if not res.parent:
        return None
    name = res.parent.name
    embedded = res.parent.from_item_id(item_id)
    if parent_id and embedded and parent_id != embedded:
        raise GraphMacosError(
            f"--{name} {parent_id} does not match the {name} in id {item_id} ({embedded})"
        )
    if not (resolved := parent_id or embedded):
        raise GraphMacosError(f"--{name} is required for id {item_id}")
    return resolved


def item_url(res: Resource, item_id: str, parent_id: str | None = None) -> str:
    return f"{_collection_url(res, resolve_parent(res, item_id, parent_id))}/{quote_id(item_id)}"


def item_urls(res: Resource, ids: Sequence[str], parent_id: str | None = None) -> dict[str, str]:
    """URL per id. Raises on any bad id, so callers can validate before sending anything."""
    return {i: item_url(res, i, parent_id) for i in ids}


def shape(res: Resource, record: dict, parent_id: str | None = None) -> dict:
    """What gets emitted: redacted fields removed, derived fields and parent tag added."""
    out = {k: v for k, v in record.items() if k not in res.redact}
    if res.enrich:
        out.update(res.enrich(out))
    if res.parent and res.parent.tag and parent_id:
        out[res.parent.tag] = parent_id
    return out


def list_(
    g: GraphClient,
    res: Resource,
    parent_ids: Sequence[str] = (),
    *,
    filter: str | None = None,
    select: str | None = None,
    limit: int | None = None,
    default_filter: bool = True,
    search: str | None = None,
) -> Iterator[dict]:
    """Every record in the collection (once per parent id for sub-resources).

    `search` is a `$search` expression. Entra directory objects only accept it together with
    `ConsistencyLevel: eventual` and `$count=true`, which are sent for you (the header on
    every page). Only resources with `supports_search` accept it.
    """
    if search and not res.supports_search:
        raise GraphMacosError(f"{res.noun} does not support --search")
    if res.parent:
        if not parent_ids:
            raise GraphMacosError(f"at least one {res.parent.name} id is required")
        parents: list[str | None] = list(parent_ids)
    else:
        parents = [None]

    params: dict[str, Any] = {"$top": min(limit, PAGE_SIZE) if limit else PAGE_SIZE}
    if odata_filter := combine_filters(res.default_filter if default_filter else None, filter):
        params["$filter"] = odata_filter
    if fields := select or res.default_select:
        params["$select"] = fields
    extra: dict[str, Any] = {}
    if search:
        params["$search"] = search
        params["$count"] = "true"
        extra["headers"] = {"ConsistencyLevel": "eventual"}

    def records() -> Iterator[dict]:
        for parent_id in parents:
            for record in g.paged(_collection_url(res, parent_id), params=dict(params), **extra):
                yield shape(res, record, parent_id)

    return itertools.islice(records(), limit) if limit else records()


def get(
    g: GraphClient, res: Resource, ids: Sequence[str], *, parent_id: str | None = None
) -> Iterator[dict]:
    """Fetch records by id. Fails on the first error (a GraphError with Graph's message)."""
    urls = item_urls(res, ids, parent_id)
    for i in ids:
        record = g.get(urls[i])
        record.pop("@odata.context", None)
        yield shape(res, record, resolve_parent(res, i, parent_id))


def _send(
    g: GraphClient,
    method: str,
    targets: list[tuple[dict, str]],
    bodies: Sequence[dict] | None = None,
) -> Iterator[dict]:
    """Run one write per target through $batch; yield `{**label, status, error?}` each."""
    requests_: list[dict] = []
    for n, (_, url) in enumerate(targets):
        req: dict[str, Any] = {"method": method, "url": url}
        if bodies is not None:
            req["headers"] = {"Content-Type": "application/json"}
            req["body"] = bodies[n]
        requests_.append(req)
    for (label, _), resp in zip(targets, g.batch(requests_), strict=True):
        ok = 200 <= resp["status"] < 300
        result = {**label, "status": _PAST_TENSE[method] if ok else "failed"}
        if ok and method == "POST":
            result["id"] = (resp.get("body") or {}).get("id")
        if not ok:
            result["error"] = batch_error(resp)
        yield result


def delete(
    g: GraphClient, res: Resource, ids: Sequence[str], *, parent_id: str | None = None
) -> Iterator[dict]:
    urls = item_urls(res, ids, parent_id)
    return _send(g, "DELETE", [({res.id_key: i}, urls[i]) for i in ids])


def update(
    g: GraphClient,
    res: Resource,
    ids: Sequence[str],
    patch: dict,
    *,
    parent_id: str | None = None,
) -> Iterator[dict]:
    if res.id_key in patch:
        raise GraphMacosError(f"{res.id_key!r} cannot be updated")
    urls = item_urls(res, ids, parent_id)
    return _send(g, "PATCH", [({res.id_key: i}, urls[i]) for i in ids], [patch] * len(ids))


def create(
    g: GraphClient, res: Resource, bodies: Iterable[dict], *, parent_id: str | None = None
) -> Iterator[dict]:
    """Create one record per body. Results carry `index` (input order) and the new `id`."""
    url = _collection_url(res, parent_id)
    items = list(bodies)
    return _send(g, "POST", [({"index": n}, url) for n in range(len(items))], items)
