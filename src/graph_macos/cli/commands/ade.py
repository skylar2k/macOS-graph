import logging
from collections.abc import Callable

import click

from ...graph.api import API_VERSION
from ...graph.ids import dep_profile_split_guid, resolve_token_id
from ...resources import ade
from .. import runtime
from ..factory import GraphCommand, report
from ..utils import safety
from ..utils.pipe import clean_id, collect_ids

log = logging.getLogger(__name__)


@click.command("assign", cls=GraphCommand, scopes=[ade.WRITE_SCOPE], writes=True)
@click.argument("serials", nargs=-1, metavar="SERIAL...")
@click.option(
    "--profile",
    required=True,
    help="Enrollment profile id: the full ECV2_… id or just its trailing GUID.",
)
@click.option("--token", help="ADE token id. Optional when --profile is a full ECV2_… id.")
@click.option(
    "--key", default="serialNumber", show_default=True, help="Field holding the serial on stdin."
)
@click.option(
    "--chunk-size",
    type=click.IntRange(min=1),
    default=100,
    show_default=True,
    help="Serials per request.",
)
@safety.options
def assign(
    serials: tuple[str, ...],
    profile: str,
    token: str | None,
    key: str,
    chunk_size: int,
    yes: bool,
    max_items: int,
) -> int:
    """Assign an enrollment profile to devices by serial number.

    Serials come from the arguments or stdin (objects with a serialNumber field, e.g.
    `gmac devices list` output, or one serial per line). Dry run unless --yes.
    """
    profile = clean_id(profile)
    token_id = resolve_token_id(profile, clean_id(token) if token else None)
    profile_id = dep_profile_split_guid(profile)
    serial_list = collect_ids(serials, key)
    records = [{"serialNumber": s, "profile": profile_id} for s in serial_list]
    if not safety.proceed(yes, max_items, records, "assign enrollment profile"):
        return 0
    g = runtime.make_graph([ade.WRITE_SCOPE], API_VERSION.BETA)
    return report(ade.assign_profile(g, token_id, profile_id, serial_list, chunk_size), "assigned")


def register(group_for: Callable[[tuple[str, ...]], click.Group]) -> None:
    group_for(("ade", "profiles")).add_command(assign)
