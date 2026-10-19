import argparse
import logging

from ..graph import API_VERSION, Graph, batch_error
from ..graph.ids import quote_id
from .utils import safety
from .utils.pipe import collect_ids, emit, entrypoint, setup_logging

log = logging.getLogger("delete_devices")

SCOPES = ["DeviceManagementManagedDevices.ReadWrite.All"]


@entrypoint
def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Delete Intune managed devices. Device ids come from the arguments, or from "
            "stdin (NDJSON objects with an 'id' field, or one bare id per line). Emits one "
            "result per device as NDJSON. Dry run unless --yes is given."
        )
    )
    p.add_argument("ids", nargs="*", metavar="DEVICE_ID", help="default: read stdin")
    p.add_argument("--key", default="id", help="field holding the device id (default: id)")
    p.add_argument("-v", "--verbose", action="store_true")
    safety.add_args(p)
    args = p.parse_args()
    setup_logging(args.verbose)

    ids = collect_ids(args.ids, args.key)
    if not safety.proceed(args, [{"id": i} for i in ids], "delete devices"):
        return 0

    g = Graph(scopes=SCOPES, api_ver=API_VERSION.V1)
    failed = 0
    responses = g.batch(
        {"method": "DELETE", "url": f"/deviceManagement/managedDevices/{quote_id(i)}"} for i in ids
    )
    for device_id, resp in zip(ids, responses, strict=True):
        ok = resp["status"] in (200, 204)
        failed += not ok
        result = {"id": device_id, "status": "deleted" if ok else "failed"}
        if not ok:
            result["error"] = batch_error(resp)
        emit(result)

    log.info("%d deleted, %d failed", len(ids) - failed, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    main()
