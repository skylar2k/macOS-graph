import argparse

from ..graph import API_VERSION, Graph
from ..graph.ids import profile_guid, quote_id
from .utils.pipe import collect_ids, emit, entrypoint, setup_logging

SCOPES = ["DeviceManagementServiceConfig.Read.All"]


@entrypoint
def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "List imported ADE devices from Apple for one or more ADE tokens as NDJSON. "
            "Token ids come from the arguments, or from stdin (e.g. the output of "
            "get-ade-tokens). Each device is tagged with its depOnboardingSettingId and, "
            "when it has a profile, requestedProfileId (the bare GUID of "
            "requestedEnrollmentProfileId, comparable to get-enrollment-profiles' profileId)."
        )
    )
    p.add_argument(
        "ids", nargs="*", metavar="TOKEN_ID", help="ADE token id(s); default: read stdin"
    )
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    setup_logging(args.verbose)

    g = Graph(scopes=SCOPES, api_ver=API_VERSION.BETA)
    for token_id in collect_ids(args.ids):
        for device in g.paged(
            f"/deviceManagement/depOnboardingSettings/{quote_id(token_id)}/importedAppleDeviceIdentities"
        ):
            emit(device)
    return 0


if __name__ == "__main__":
    main()
