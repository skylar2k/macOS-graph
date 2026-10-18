"""Convention for destructive scripts: dry run by default, `--yes` to act.

safety.add_args(parser)
ids = collect_ids(args.ids)
if not safety.proceed(args, [{"id": i} for i in ids], "delete devices"):
    return 0
...do the destructive thing...
"""

import argparse
import logging
from collections.abc import Sequence

from .pipe import emit

log = logging.getLogger(__name__)

DEFAULT_MAX_ITEMS = 50


def add_args(parser: argparse.ArgumentParser, max_items: int = DEFAULT_MAX_ITEMS) -> None:
    g = parser.add_argument_group("safety")
    g.add_argument(
        "--yes", action="store_true", help="actually perform the action (default: dry run)"
    )
    g.add_argument(
        "--max-items",
        type=int,
        default=max_items,
        help=f"refuse to act on more than this many records (default: {max_items})",
    )


def proceed(args: argparse.Namespace, records: Sequence[dict], what: str) -> bool:
    """Return True if the caller should perform the action.

    Without --yes, emits each record with status "dry-run" and returns False.
    With --yes, exits with an error if there are more than --max-items records.
    """
    n = len(records)
    if not args.yes:
        log.warning("dry run: would %s for %d record(s); pass --yes to proceed", what, n)
        for rec in records:
            emit({**rec, "status": "dry-run"})
        return False
    if n > args.max_items:
        raise SystemExit(
            f"error: refusing to {what} for {n} records (> --max-items {args.max_items}); "
            "raise --max-items if this is intended"
        )
    return True
