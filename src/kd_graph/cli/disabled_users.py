import csv
import sys

from ..graph import Graph
from ..pipe import entrypoint

SCOPES = ["User.Read.All"]


@entrypoint
def main() -> None:
    g = Graph(scopes=SCOPES)

    w = csv.writer(sys.stdout)
    w.writerow(["upn", "name"])
    for u in g.paged(
        "/users",
        params={
            "$filter": "accountEnabled eq false",
            "$select": "userPrincipalName,displayName",
            "$top": 999,
        },
    ):
        w.writerow([u["userPrincipalName"], u["displayName"]])


if __name__ == "__main__":
    main()
