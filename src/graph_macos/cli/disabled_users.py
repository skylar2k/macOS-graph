import argparse

from ..graph import Graph
from .utils.pipe import emit, entrypoint, setup_logging

SCOPES = ["User.Read.All"]


@entrypoint
def main() -> int:
    p = argparse.ArgumentParser(description="List disabled users as NDJSON, one user per line.")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    setup_logging(args.verbose)

    g = Graph(scopes=SCOPES)
    for user in g.paged(
        "/users",
        params={
            "$filter": "accountEnabled eq false",
            "$select": "id,userPrincipalName,displayName",
            "$top": 999,
        },
    ):
        emit(user)
    return 0


if __name__ == "__main__":
    main()
