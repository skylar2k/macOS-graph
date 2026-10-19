"""The `gmac` command: one entry point, nouns and verbs built from the resource registry."""

import importlib
import sys

import click

from ..errors import GraphMacosError
from ..resources import RESOURCES
from .commands import CUSTOM
from .factory import build_commands
from .utils.pipe import entrypoint, setup_logging

GROUP_HELP: dict[tuple[str, ...], str] = {
    ("ade",): "Apple Automated Device Enrollment: tokens, enrollment profiles, devices.",
}


class CliError(click.ClickException):
    """A user-facing failure, shown as `error: <message>` with exit code 1."""

    def show(self, file=None) -> None:
        click.echo(f"error: {self.format_message()}", file=file or sys.stderr)


class Root(click.Group):
    def invoke(self, ctx: click.Context):
        try:
            return super().invoke(ctx)
        except GraphMacosError as e:  # includes AuthError and GraphError
            raise CliError(str(e)) from e


@click.group(
    cls=Root,
    context_settings={"help_option_names": ["-h", "--help"]},
    help=(
        "Pipe-friendly Microsoft Graph tools. Commands print NDJSON (one record per line) "
        "and read ids from arguments or stdin; changes are dry runs unless --yes."
    ),
)
@click.version_option(package_name="graph-macos")
@click.option("-v", "--verbose", is_flag=True, help="Debug logging on stderr.")
def cli(verbose: bool) -> None:
    setup_logging(verbose)


def _ensure_group(root: click.Group, path: tuple[str, ...], help: str | None = None) -> click.Group:
    group = root
    for depth, name in enumerate(path, 1):
        sub = group.commands.get(name)
        if sub is None:
            sub = click.Group(
                name,
                help=GROUP_HELP.get(path[:depth]),
                context_settings={"help_option_names": ["-h", "--help"]},
            )
            group.add_command(sub)
        if not isinstance(sub, click.Group):
            raise TypeError(f"{'/'.join(path[:depth])} is a command, not a group")
        group = sub
    if help and not group.help:
        group.help = help
    return group


def build() -> click.Group:
    """Assemble the full command tree (no network, no msal/requests import)."""
    root = cli
    for res in RESOURCES:
        group = _ensure_group(root, res.path, res.help)
        for command in build_commands(res):
            group.add_command(command)
    for module in CUSTOM:
        importlib.import_module(module).register(lambda path: _ensure_group(root, path))
    return root


build()


@entrypoint
def main() -> int:
    try:
        return cli.main(standalone_mode=False, prog_name="gmac") or 0
    except click.exceptions.Abort:
        print(file=sys.stderr)
        return 130
    except click.ClickException as e:
        e.show()
        return e.exit_code
