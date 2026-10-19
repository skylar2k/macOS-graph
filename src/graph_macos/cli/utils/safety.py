"""Convention for write commands: dry run by default, `--yes` to act.

    @safety.options
    def cmd(..., yes, max_items):
        if not safety.proceed(yes, max_items, records, "delete devices"):
            return 0
        ...do the write...

Apply the decorator last (outermost) so the options appear after the command's own.
"""

import logging
from collections.abc import Callable, Sequence
from typing import Any

import click

from ...errors import GraphMacosError
from .pipe import emit

log = logging.getLogger(__name__)

DEFAULT_MAX_ITEMS = 50


def options(f: Callable[..., Any]) -> Callable[..., Any]:
    f = click.option(
        "--max-items",
        type=click.IntRange(min=1),
        default=DEFAULT_MAX_ITEMS,
        show_default=True,
        help="Refuse to act on more records than this.",
    )(f)
    return click.option(
        "--yes", is_flag=True, help="Actually perform the change (default: dry run)."
    )(f)


def proceed(yes: bool, max_items: int, records: Sequence[dict], what: str) -> bool:
    """Return True if the caller should perform the change.

    Without --yes, emits each record with status "dry-run" and returns False.
    With --yes, raises if there are more than `max_items` records.
    """
    n = len(records)
    if not yes:
        log.warning("dry run: would %s for %d record(s); pass --yes to proceed", what, n)
        for rec in records:
            emit({**rec, "status": "dry-run"})
        return False
    if n > max_items:
        raise GraphMacosError(
            f"refusing to {what} for {n} records (> --max-items {max_items}); "
            "raise --max-items if this is intended"
        )
    return True
