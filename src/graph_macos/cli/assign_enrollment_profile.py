import argparse
import itertools
import logging
from collections.abc import Iterator

from ..graph import API_VERSION, Graph, GraphError
from .utils import safety
from .utils.pipe import collect_ids, emit, entrypoint, setup_logging

log = logging.getLogger("assign_enrollment_profile")

SCOPES = ["DeviceManagementServiceConfig.ReadWrite.All"]


def assign(
    g: Graph, token_id: str, profile_id: str, serials: list[str], chunk_size: int
) -> Iterator[dict]:
    """Assign the profile to devices by serial number, one request per chunk.

    Yields one result per serial. A failing chunk marks its serials failed and the
    rest carry on.
    """
    url = (
        f"/deviceManagement/depOnboardingSettings/{token_id}"
        f"/enrollmentProfiles/{profile_id}/updateDeviceProfileAssignment"
    )
    for chunk in itertools.batched(serials, chunk_size, strict=False):
        try:
            g.request("POST", url, json={"deviceIds": list(chunk)})
        except GraphError as e:
            log.error("chunk of %d failed: %s", len(chunk), e)
            yield from ({"serialNumber": s, "status": "failed", "error": str(e)} for s in chunk)
        else:
            yield from ({"serialNumber": s, "status": "assigned"} for s in chunk)


@entrypoint
def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Assign an ADE enrollment profile to devices by serial number. Serials come "
            "from the arguments, or from stdin (NDJSON objects with a 'serialNumber' "
            "field, e.g. get-devices output, or one bare serial per line). "
            "Emits one result per device as NDJSON. Dry run unless --yes is given."
        )
    )
    p.add_argument("serials", nargs="*", metavar="SERIAL", help="default: read stdin")
    p.add_argument("--token", required=True, help="ADE token id (depOnboardingSettingId)")
    p.add_argument("--profile", required=True, help="enrollment profile id")
    p.add_argument(
        "--key", default="serialNumber", help="field holding the serial (default: serialNumber)"
    )
    p.add_argument("--chunk-size", type=int, default=100, help="serials per request (default: 100)")
    p.add_argument("-v", "--verbose", action="store_true")
    safety.add_args(p)
    args = p.parse_args()
    setup_logging(args.verbose)

    serials = collect_ids(args.serials, args.key)
    records = [{"serialNumber": s, "profile": args.profile} for s in serials]
    if not safety.proceed(args, records, "assign enrollment profile"):
        return 0

    g = Graph(scopes=SCOPES, api_ver=API_VERSION.BETA)
    failed = 0
    for result in assign(g, args.token, args.profile, serials, args.chunk_size):
        failed += result["status"] == "failed"
        emit(result)

    log.info("%d assigned, %d failed", len(serials) - failed, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    main()
