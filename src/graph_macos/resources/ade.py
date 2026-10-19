"""Apple Automated Device Enrollment (ADE): tokens, enrollment profiles, imported devices."""

import itertools
import logging
from collections.abc import Iterator, Sequence

from ..graph.api import API_VERSION, GraphClient
from ..graph.ids import dep_profile_split_guid, quote_id, token_id_from_dep_profile_id
from .base import READ_VERBS, Parent, Resource
lazy from ..graph.client import GraphError

log = logging.getLogger(__name__)

READ_SCOPE = "DeviceManagementServiceConfig.Read.All"
WRITE_SCOPE = "DeviceManagementServiceConfig.ReadWrite.All"
_TOKEN = Parent("token", from_item_id=token_id_from_dep_profile_id)

TOKENS = Resource(
    path=("ade", "tokens"),
    collection="/deviceManagement/depOnboardingSettings",
    help="ADE tokens.",
    read_scopes=(READ_SCOPE,),
    api=API_VERSION.BETA,
)

PROFILES = Resource(
    path=("ade", "profiles"),
    collection="/deviceManagement/depOnboardingSettings/{parent}/enrollmentProfiles",
    help="ADE enrollment profiles. Full ECV2_… ids carry their token, so --token is optional.",
    read_scopes=(READ_SCOPE,),
    write_scopes=(WRITE_SCOPE,),
    verbs=READ_VERBS | {"update"},
    api=API_VERSION.BETA,
    parent=_TOKEN,
    odata_type="#microsoft.graph.depMacOSEnrollmentProfile",
    redact=frozenset({"adminAccountPassword"}),
    enrich=lambda rec: {"profileId": dep_profile_split_guid(rec["id"])},
)

DEVICES = Resource(
    path=("ade", "devices"),
    collection="/deviceManagement/depOnboardingSettings/{parent}/importedAppleDeviceIdentities",
    help="Devices imported from Apple for an ADE token.",
    read_scopes=(READ_SCOPE,),
    api=API_VERSION.BETA,
    parent=Parent("token"),
    verbs=frozenset({"list"}),
)

RESOURCES = (TOKENS, PROFILES, DEVICES)


def assign_profile(
    g: GraphClient, token_id: str, profile_id: str, serials: Sequence[str], chunk_size: int = 100
) -> Iterator[dict]:
    """Assign a profile (bare GUID) to devices by serial number, one request per chunk.

    Yields one result per serial. A failing chunk marks its serials failed and the rest
    carry on.
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
