from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EntityType(str, Enum):
    LOCATION = 'location'
    USER = 'user'
    WORKSPACE = 'workspace'


class Stage(str, Enum):
    LOCATION_CREATE_AND_ACTIVATE = 'location_create_and_activate'
    LOCATION_ROUTE_GROUP_RESOLVE = 'location_route_group_resolve'
    LOCATION_PSTN_CONFIGURE = 'location_pstn_configure'
    LOCATION_NUMBERS_ADD_DISABLED = 'location_numbers_add_disabled'
    LOCATION_MAIN_DDI_ASSIGN = 'location_main_ddi_assign'
    LOCATION_INTERNAL_CALLING_CONFIG = 'location_internal_calling_config'
    LOCATION_OUTGOING_PERMISSION_DEFAULT = 'location_outgoing_permission_default'
    USER_LEGACY_INTERCOM_SECONDARY = 'user_legacy_intercom_secondary'
    USER_LEGACY_FORWARD_PREFIX_53 = 'user_legacy_forward_prefix_53'
    USER_OUTGOING_PERMISSION_OVERRIDE = 'user_outgoing_permission_override'
    WORKSPACE_LEGACY_INTERCOM_SECONDARY = 'workspace_legacy_intercom_secondary'
    WORKSPACE_LEGACY_FORWARD_PREFIX_53 = 'workspace_legacy_forward_prefix_53'
    WORKSPACE_OUTGOING_PERMISSION_OVERRIDE = 'workspace_outgoing_permission_override'


@dataclass(frozen=True)
class LocationInput:
    row_number: int
    location_name: str
    location_id: str | None
    org_id: str | None
    route_group_id: str | None
    main_number: str | None
    default_outgoing_profile: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class UserInput:
    row_number: int
    user_email: str
    user_id: str | None
    location_name: str | None
    location_id: str | None
    extension: str | None
    legacy_secondary_number: str | None
    legacy_forward_target: str | None
    outgoing_profile: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class WorkspaceInput:
    row_number: int
    workspace_name: str
    workspace_id: str | None
    location_name: str | None
    location_id: str | None
    extension: str | None
    legacy_secondary_number: str | None
    legacy_forward_target: str | None
    outgoing_profile: str | None
    payload: dict[str, Any]


@dataclass
class PlannedAction:
    entity_type: EntityType
    entity_key: str
    stage: Stage
    mode: str
    details: str


@dataclass
class RunSummary:
    run_id: str
    mode: str
    completed_count: int
    failed_count: int
    planned_count: int
    outputs: dict[str, str] = field(default_factory=dict)
