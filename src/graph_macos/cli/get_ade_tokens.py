import argparse

from ..graph import API_VERSION, Graph
from .utils.pipe import emit, entrypoint, setup_logging

SCOPES = ["DeviceManagementServiceConfig.Read.All"]


@entrypoint
def main() -> int:
    p = argparse.ArgumentParser(description="List ADE tokens as NDJSON, one token per line.")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    setup_logging(args.verbose)

    g = Graph(scopes=SCOPES, api_ver=API_VERSION.BETA)
    for token in g.paged("/deviceManagement/depOnboardingSettings"):
        emit(token)
    return 0


if __name__ == "__main__":
    main()
