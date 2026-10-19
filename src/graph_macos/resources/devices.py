from ..graph.api import API_VERSION
from .base import Resource

DEVICES = Resource(
    path=("devices",),
    collection="/deviceManagement/managedDevices",
    help="Intune managed devices (macOS only by default).",
    read_scopes=("DeviceManagementManagedDevices.Read.All",),
    write_scopes=("DeviceManagementManagedDevices.ReadWrite.All",),
    verbs=frozenset({"list", "get", "delete"}),
    api=API_VERSION.V1,
    default_select=(
        "id,deviceName,serialNumber,userPrincipalName,operatingSystem,osVersion,"
        "complianceState,lastSyncDateTime"
    ),
    default_filter="operatingSystem eq 'macOS'",
)

RESOURCES = (DEVICES,)
