import argparse

from ..graph import API_VERSION, Graph
from .utils.pipe import collect_ids, emit, entrypoint, setup_logging

SCOPES = ["DeviceManagementServiceConfig.Read.All"]


@entrypoint
def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "List enrollment profiles for one or more ADE tokens as NDJSON. Token ids "
            "come from the arguments, or from stdin (e.g. the output of "
            "get-ade-tokens). Each profile is tagged with its depOnboardingSettingId."
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
        for profile in g.paged(
            f"/deviceManagement/depOnboardingSettings/{token_id}/enrollmentProfiles"
        ):
            emit({**profile, "depOnboardingSettingId": token_id})
    return 0


if __name__ == "__main__":
    main()
