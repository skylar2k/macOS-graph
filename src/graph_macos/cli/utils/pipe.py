"""Helpers for scripts that sit in a unix pipeline.

Convention: records travel as JSON, one object per line (NDJSON) on stdout.
Diagnostics go to stderr so stdout stays clean for the next stage.
"""

import functools
import json
import logging
import os
import sys
from collections.abc import Callable, Iterable, Iterator, Sequence
from typing import Any, TextIO

from ...errors import GraphMacosError


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


def emit(record: Any, out: TextIO | None = None) -> None:
    out = out or sys.stdout  # resolved at call time so redirection/capture works
    out.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")


def emit_all(records: Iterable[Any]) -> None:
    for r in records:
        emit(r)


def read_records(stream: TextIO | None = None) -> Iterator[Any]:
    """Read JSON values from a stream.

    Accepts NDJSON, concatenated/pretty-printed values (jq's default output) and
    top-level arrays (flattened). If the input isn't JSON at all, e.g. the output
    of `jq -r '.id'`, each non-blank line is yielded as a string.
    """
    stream = stream or sys.stdin
    if stream.isatty():
        raise GraphMacosError("expected input on stdin (pipe something in)")
    text = stream.read()

    decoder = json.JSONDecoder()
    values: list[Any] = []
    pos = 0
    try:
        while pos < len(text):
            if text[pos].isspace():
                pos += 1
                continue
            value, pos = decoder.raw_decode(text, pos)
            values.append(value)
    except json.JSONDecodeError:
        yield from (line.strip() for line in text.splitlines() if line.strip())
        return

    for v in values:
        if isinstance(v, list):
            yield from v
        else:
            yield v


def read_ids(key: str = "id", stream: TextIO | None = None) -> Iterator[str]:
    """Yield ids from stdin records: objects (using `key`) or bare strings."""
    for n, rec in enumerate(read_records(stream), 1):
        if isinstance(rec, dict):
            if key not in rec:
                raise GraphMacosError(f"record {n} has no {key!r} field")
            yield str(rec[key])
        else:
            yield str(rec)


def clean_id(value: str) -> str:
    """Trim whitespace and unwrap a JSON string, e.g. the `"abc"` that `jq .id` prints
    (without -r) when captured with $(...)."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value
        if isinstance(decoded, str):
            return decoded.strip()
    return value


def collect_ids(cli_ids: Sequence[str] = (), key: str = "id") -> list[str]:
    """Ids from the command line if given, otherwise from stdin; de-duplicated, order kept.

    Typical use: `p.add_argument("ids", nargs="*")` then `collect_ids(args.ids)`.
    """
    ids = [clean_id(i) for i in cli_ids] or read_ids(key)
    return list(dict.fromkeys(ids))


def entrypoint(main: Callable[[], int | None]) -> Callable[[], None]:
    """Decorator for a CLI main(): clean errors, quiet on `| head`, Ctrl-C exit code.

    The result is usable directly as a console-script entry point.
    """

    @functools.wraps(main)
    def wrapper() -> None:
        try:
            sys.exit(main() or 0)
        except GraphMacosError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
        except BrokenPipeError:
            # Downstream closed early; stop Python's flush-at-exit from complaining.
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
            sys.exit(1)
        except KeyboardInterrupt:
            sys.exit(130)

    return wrapper
