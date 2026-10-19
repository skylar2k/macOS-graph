"""Verbs that don't fit the generic list/get/create/update/delete shape.

Each module here exposes `register(group_for)`, where `group_for(path)` returns the click
group for a CLI path such as ("ade", "profiles"), creating it if needed. List new modules
in `CUSTOM` so the app loads them.
"""

CUSTOM = ("graph_macos.cli.commands.ade",)
