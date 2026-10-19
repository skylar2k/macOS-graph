"""Build click commands from `Resource` specs.

Each supported verb becomes `gmac <path...> <verb>`. Read verbs ask only for the resource's
read scopes; write verbs ask for its write scopes and get the dry-run safety convention.
"""

import logging
from collections.abc import Callable, Iterable
from typing import Any

import click

from ..errors import GraphMacosError
from ..resources import base, payload
from ..resources.base import Resource
from . import runtime
from .utils import safety
from .utils.pipe import clean_id, collect_ids, emit, read_records

log = logging.getLogger(__name__)

VERB_ORDER = ("list", "get", "create", "update", "delete")


def _label(res: Resource) -> str:
    return " ".join(res.path)


class GraphCommand(click.Command):
    """A command that records what Graph access it needs, for the generated docs and tests."""

    def __init__(self, *args: Any, scopes: Iterable[str], writes: bool, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.scopes = tuple(scopes)
        self.writes = writes


def _apply(fn: Callable[..., Any], decorators: list[Callable[..., Any]]) -> Callable[..., Any]:
    for decorator in reversed(decorators):
        fn = decorator(fn)
    return fn


def report(results: Iterable[dict], what: str) -> int:
    """Emit write results; exit with code 1 if any failed."""
    n = failed = 0
    for result in results:
        n += 1
        failed += result["status"] == "failed"
        emit(result)
    log.info("%d %s, %d failed", n - failed, what, failed)
    if failed:
        raise click.exceptions.Exit(1)  # honoured with or without standalone_mode
    return 0


def _parent_option(res: Resource) -> list[Callable[..., Any]]:
    if not res.parent:
        return []
    name = res.parent.name
    return [
        click.option(
            f"--{name}",
            "parent_id",
            help=f"{name.capitalize()} id. Optional when ids already contain it.",
        )
    ]


def _id_args(res: Resource) -> list[Callable[..., Any]]:
    return [
        click.argument("ids", nargs=-1, metavar="ID..."),
        click.option(
            "--key",
            default=res.id_key,
            show_default=True,
            help="Field holding the id when reading records from stdin.",
        ),
    ]


def _patch_options() -> list[Callable[..., Any]]:
    return [
        click.option(
            "--set",
            "set_items",
            multiple=True,
            metavar="KEY=VALUE",
            help="Property to set; VALUE is JSON if it parses, else a string. Repeatable.",
        ),
        click.option("--patch", "patch_json", metavar="JSON", help="JSON object of properties."),
        click.option(
            "--patch-file", metavar="PATH", help="File containing a JSON object of properties."
        ),
    ]


def _masked(res: Resource, body: dict) -> dict:
    return {k: "***" if k in res.redact else v for k, v in body.items()}


def _warn_secrets(res: Resource, set_items: Iterable[str]) -> None:
    for key in res.redact & {item.partition("=")[0] for item in set_items}:
        log.warning("%s given via --set is visible in shell history; prefer --patch-file", key)


def _list_cmd(res: Resource) -> GraphCommand:
    decorators: list[Callable[..., Any]] = []
    if res.parent:
        name = res.parent.name
        decorators += [
            click.argument("parents", nargs=-1, metavar=f"{name.upper()}_ID..."),
            click.option(
                "--key", default="id", show_default=True, help="Field holding the id on stdin."
            ),
        ]
    decorators += [
        click.option("--filter", "filter_", metavar="ODATA", help="OData $filter."),
        click.option("--select", metavar="FIELDS", help="Comma-separated properties to return."),
        click.option("--limit", type=click.IntRange(min=1), help="Stop after this many records."),
    ]
    if res.supports_search:
        decorators.append(
            click.option(
                "--search",
                metavar="EXPR",
                help="$search expression, e.g. '\"displayName:Contoso\"' (quotes included).",
            )
        )
    if res.default_filter:
        decorators.append(
            click.option(
                "--no-default-filter",
                is_flag=True,
                help=f"Drop the built-in filter ({res.default_filter}).",
            )
        )

    def callback(**kw: Any) -> int:
        parents = collect_ids(kw.get("parents", ()), kw["key"]) if res.parent else []
        if res.parent and not parents:
            raise GraphMacosError(f"at least one {res.parent.name} id is required")
        g = runtime.make_graph(res.read_scopes, res.api)
        search = kw.get("search")
        try:
            for record in base.list_(
                g,
                res,
                parents,
                filter=kw["filter_"],
                select=kw["select"],
                limit=kw["limit"],
                default_filter=not kw.get("no_default_filter", False),
                search=search,
            ):
                emit(record)
        except GraphMacosError as e:
            if res.supports_search and not search and "ConsistencyLevel" in str(e):
                raise GraphMacosError(
                    f"{e}\nhint: Graph wants advanced query mode for this filter, which gmac only "
                    "enables for --search; filter client-side with jq instead"
                ) from e
            raise
        return 0

    source = (
        f" {res.parent.name.capitalize()} ids come from arguments or stdin." if res.parent else ""
    )
    return click.command(
        "list",
        cls=GraphCommand,
        scopes=res.read_scopes,
        writes=False,
        help=f"List {_label(res)} as NDJSON, one record per line.{source}",
    )(_apply(callback, decorators))


def _get_cmd(res: Resource) -> GraphCommand:
    def callback(ids: tuple[str, ...], key: str, parent_id: str | None = None) -> int:
        parent = clean_id(parent_id) if parent_id else None
        g = runtime.make_graph(res.read_scopes, res.api)
        for record in base.get(g, res, collect_ids(ids, key), parent_id=parent):
            emit(record)
        return 0

    return click.command(
        "get",
        cls=GraphCommand,
        scopes=res.read_scopes,
        writes=False,
        help=f"Fetch {_label(res)} by id (arguments or stdin) as NDJSON.",
    )(_apply(callback, [*_id_args(res), *_parent_option(res)]))


def _delete_cmd(res: Resource) -> GraphCommand:
    def callback(
        ids: tuple[str, ...], key: str, yes: bool, max_items: int, parent_id: str | None = None
    ) -> int:
        parent = clean_id(parent_id) if parent_id else None
        id_list = collect_ids(ids, key)
        base.item_urls(res, id_list, parent)  # fail on bad ids before anything else
        records = [{res.id_key: i} for i in id_list]
        if not safety.proceed(yes, max_items, records, f"delete {res.noun}"):
            return 0
        g = runtime.make_graph(res.write_scopes, res.api)
        return report(base.delete(g, res, id_list, parent_id=parent), "deleted")

    return click.command(
        "delete",
        cls=GraphCommand,
        scopes=res.write_scopes,
        writes=True,
        help=f"Delete {_label(res)} by id (arguments or stdin). Dry run unless --yes.",
    )(safety.options(_apply(callback, [*_id_args(res), *_parent_option(res)])))


def _update_cmd(res: Resource) -> GraphCommand:
    def callback(
        ids: tuple[str, ...],
        key: str,
        set_items: tuple[str, ...],
        patch_json: str | None,
        patch_file: str | None,
        yes: bool,
        max_items: int,
        parent_id: str | None = None,
    ) -> int:
        patch = payload.build_body(set_items, patch_json, patch_file, res.odata_type)
        _warn_secrets(res, set_items)
        parent = clean_id(parent_id) if parent_id else None
        id_list = collect_ids(ids, key)
        base.item_urls(res, id_list, parent)
        records = [{res.id_key: i, "patch": _masked(res, patch)} for i in id_list]
        if not safety.proceed(yes, max_items, records, f"update {res.noun}"):
            return 0
        g = runtime.make_graph(res.write_scopes, res.api)
        return report(base.update(g, res, id_list, patch, parent_id=parent), "updated")

    return click.command(
        "update",
        cls=GraphCommand,
        scopes=res.write_scopes,
        writes=True,
        help=(
            f"Apply the same property changes to {_label(res)} by id (arguments or stdin). "
            "Dry run unless --yes."
        ),
    )(safety.options(_apply(callback, [*_id_args(res), *_parent_option(res), *_patch_options()])))


def _create_cmd(res: Resource) -> GraphCommand:
    def callback(
        set_items: tuple[str, ...],
        patch_json: str | None,
        patch_file: str | None,
        yes: bool,
        max_items: int,
        parent_id: str | None = None,
    ) -> int:
        parent = clean_id(parent_id) if parent_id else None
        if set_items or patch_json or patch_file:
            bodies = [payload.build_body(set_items, patch_json, patch_file, res.odata_type)]
        else:
            bodies = []
            for n, rec in enumerate(read_records(), 1):
                if not isinstance(rec, dict):
                    raise GraphMacosError(f"stdin record {n} is not a JSON object")
                bodies.append({"@odata.type": res.odata_type, **rec} if res.odata_type else rec)
        records = [{"index": n, "body": _masked(res, b)} for n, b in enumerate(bodies)]
        if not safety.proceed(yes, max_items, records, f"create {res.noun}"):
            return 0
        g = runtime.make_graph(res.write_scopes, res.api)
        return report(base.create(g, res, bodies, parent_id=parent), "created")

    return click.command(
        "create",
        cls=GraphCommand,
        scopes=res.write_scopes,
        writes=True,
        help=(
            f"Create {_label(res)} from --set/--patch/--patch-file, or one per JSON object on "
            "stdin. Dry run unless --yes."
        ),
    )(safety.options(_apply(callback, [*_parent_option(res), *_patch_options()])))


_BUILDERS: dict[str, Callable[[Resource], GraphCommand]] = {
    "list": _list_cmd,
    "get": _get_cmd,
    "create": _create_cmd,
    "update": _update_cmd,
    "delete": _delete_cmd,
}


def build_commands(res: Resource) -> list[GraphCommand]:
    """The click commands for every verb the resource supports."""
    return [_BUILDERS[verb](res) for verb in VERB_ORDER if verb in res.verbs]
