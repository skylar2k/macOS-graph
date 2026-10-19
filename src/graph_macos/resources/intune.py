"""Intune configuration objects that fit the generic list/get/delete shape.

Updating these needs the derived `@odata.type` of each object, so they stay read/delete
until a use case shows what an update command should look like.
"""

from ..graph.api import API_VERSION
from .base import Resource

_VERBS = frozenset({"list", "get", "delete"})

COMPLIANCE_POLICIES = Resource(
    path=("compliance-policies",),
    collection="/deviceManagement/deviceCompliancePolicies",
    help="Intune device compliance policies.",
    read_scopes=("DeviceManagementConfiguration.Read.All",),
    write_scopes=("DeviceManagementConfiguration.ReadWrite.All",),
    verbs=_VERBS,
    api=API_VERSION.V1,
    default_select="id,displayName,description,lastModifiedDateTime",
)

CONFIGURATION_PROFILES = Resource(
    path=("configuration-profiles",),
    collection="/deviceManagement/deviceConfigurations",
    help="Intune device configuration profiles.",
    read_scopes=("DeviceManagementConfiguration.Read.All",),
    write_scopes=("DeviceManagementConfiguration.ReadWrite.All",),
    verbs=_VERBS,
    api=API_VERSION.V1,
    default_select="id,displayName,description,lastModifiedDateTime",
)

APPS = Resource(
    path=("apps",),
    collection="/deviceAppManagement/mobileApps",
    help="Intune apps.",
    read_scopes=("DeviceManagementApps.Read.All",),
    write_scopes=("DeviceManagementApps.ReadWrite.All",),
    verbs=_VERBS,
    api=API_VERSION.V1,
    default_select="id,displayName,publisher,lastModifiedDateTime",
)

RESOURCES = (COMPLIANCE_POLICIES, CONFIGURATION_PROFILES, APPS)
