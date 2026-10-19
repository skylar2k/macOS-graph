import argparse
import itertools
import logging
from collections.abc import Iterator

from ..graph import API_VERSION, Graph, GraphError
from ..graph.ids import profile_guid, quote_id, token_id_from_profile_id
from .utils import safety
from .utils.pipe import clean_id, collect_ids, emit, entrypoint, setup_logging

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
        f"/deviceManagement/depOnboardingSettings/{quote_id(token_id)}"
        f"/enrollmentProfiles/{quote_id(profile_id)}/updateDeviceProfileAssignment"
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
    p.add_argument(
        "--token",
        help="ADE token id (depOnboardingSettingId); optional when --profile is a full ECV2_… id",
    )
    p.add_argument(
        "--profile",
        required=True,
        help="enrollment profile id; the full ECV2_… id or just the trailing GUID",
    )
    p.add_argument(
        "--key", default="serialNumber", help="field holding the serial (default: serialNumber)"
    )
    p.add_argument("--chunk-size", type=int, default=100, help="serials per request (default: 100)")
    p.add_argument("-v", "--verbose", action="store_true")
    safety.add_args(p)
    args = p.parse_args()
    setup_logging(args.verbose)

    args.profile = clean_id(args.profile)
    args.token = clean_id(args.token) if args.token else None
    embedded = token_id_from_profile_id(args.profile)
    if args.token and embedded and args.token != embedded:
        raise SystemExit(
            f"error: --token {args.token} does not match the token in --profile ({embedded})"
        )
    token_id = args.token or embedded
    if not token_id:
        raise SystemExit("error: --token is required unless --profile is a full ECV2_… id")
    profile_id = profile_guid(args.profile)
    serials = collect_ids(args.serials, args.key)
    records = [{"serialNumber": s, "profile": profile_id} for s in serials]
    if not safety.proceed(args, records, "assign enrollment profile"):
        return 0

    g = Graph(scopes=SCOPES, api_ver=API_VERSION.BETA)
    failed = 0
    for result in assign(g, token_id, profile_id, serials, args.chunk_size):
        failed += result["status"] == "failed"
        emit(result)

    log.info("%d assigned, %d failed", len(serials) - failed, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    main()
