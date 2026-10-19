"""Generate the README command table from the command tree.

uv run python -m graph_macos.cli.docs --write    # refresh README.md
uv run python -m graph_macos.cli.docs --check    # exit 1 if it is stale (used by tests)
"""

import sys
from collections.abc import Iterator
from pathlib import Path

import click

from .factory import GraphCommand

START, END = "<!-- commands:start -->", "<!-- commands:end -->"


def iter_commands(
    group: click.Group, prefix: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], GraphCommand]]:
    for name in sorted(group.commands):
        cmd = group.commands[name]
        if isinstance(cmd, click.Group):
            yield from iter_commands(cmd, (*prefix, name))
        elif isinstance(cmd, GraphCommand):
            yield (*prefix, name), cmd
        else:
            raise TypeError(f"{' '.join((*prefix, name))} is not a GraphCommand")


def command_table(root: click.Group) -> str:
    rows = ["| Command | Scopes | Does |", "| --- | --- | --- |"]
    for path, cmd in iter_commands(root):
        scopes = ", ".join(f"`{s}`" for s in cmd.scopes) or "–"
        summary = (cmd.help or "").split("\n\n")[0].replace("\n", " ").strip()
        if cmd.writes:
            summary = summary.replace(" Dry run unless --yes.", "") + " **Dry run unless `--yes`.**"
        rows.append(f"| `gmac {' '.join(path)}` | {scopes} | {summary} |")
    return "\n".join(rows)


def render(readme: str, table: str) -> str:
    start, end = readme.index(START) + len(START), readme.index(END)
    return f"{readme[:start]}\n{table}\n{readme[end:]}"


def main() -> int:
    from .app import cli

    path = Path(__file__).resolve().parents[3] / "README.md"
    readme = path.read_text()
    updated = render(readme, command_table(cli))
    if "--write" in sys.argv:
        path.write_text(updated)
        return 0
    if updated != readme:
        print("README command table is stale; run: uv run python -m graph_macos.cli.docs --write")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
