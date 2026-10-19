import argparse

from ..graph import API_VERSION, Graph
from .utils.pipe import emit, entrypoint, setup_logging

SCOPES = ["DeviceManagementManagedDevices.Read.All"]
DEFAULT_SELECT = (
    "id,deviceName,serialNumber,userPrincipalName,operatingSystem,osVersion,"
    "complianceState,lastSyncDateTime"
)


@entrypoint
def main() -> int:
    p = argparse.ArgumentParser(
        description="List Intune managed devices as NDJSON, one device per line."
    )
    p.add_argument("--os", default="macOS", help="operatingSystem filter (default: macOS)")
    p.add_argument("--filter", help="extra OData $filter, ANDed with --os")
    p.add_argument("--select", default=DEFAULT_SELECT, help="comma-separated properties")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    setup_logging(args.verbose)

    odata_filter = f"operatingSystem eq '{args.os}'"
    if args.filter:
        odata_filter += f" and ({args.filter})"

    g = Graph(scopes=SCOPES, api_ver=API_VERSION.V1)
    for device in g.paged(
        "/deviceManagement/managedDevices",
        params={"$filter": odata_filter, "$select": args.select, "$top": 999},
    ):
        emit(device)
    return 0


if __name__ == "__main__":
    main()
