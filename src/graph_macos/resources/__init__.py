"""Every Graph resource this tool knows about.

To add an endpoint, define a `Resource` in one of the modules here (or a new module) and
list it in that module's RESOURCES; the CLI picks it up from the registry below.
"""

from . import ade, devices, directory, intune
from .base import Resource

RESOURCES: tuple[Resource, ...] = (
    *devices.RESOURCES,
    *directory.RESOURCES,
    *intune.RESOURCES,
    *ade.RESOURCES,
)
