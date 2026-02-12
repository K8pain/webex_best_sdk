from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Stage(str, Enum):
    ASSIGN_CALLING_LICENSE = 'assign_calling_license'
    APPLY_NUMBERS_UPDATE = 'apply_numbers_update'
    APPLY_FORWARDING = 'apply_forwarding'
    APPLY_VOICEMAIL = 'apply_voicemail'
    APPLY_CALL_INTERCEPT = 'apply_call_intercept'
    APPLY_PERMISSIONS = 'apply_permissions_in_out'
    APPLY_CALL_QUEUE_MEMBERSHIPS = 'apply_call_queue_memberships'


class StageDecision(str, Enum):
    YES = 'yes'
    NO = 'no'
    YESBUT = 'yesbut'


@dataclass(frozen=True)
class InputRecord:
    row_number: int
    user_email: str
    calling_license_id: str
    location_id: str
    extension: str | None
    phone_number: str | None
    payload: dict[str, Any]


@dataclass
class RecordResult:
    user_email: str
    status: str
    failed_stage: str | None = None
    verified: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailureEntry:
    user_email: str
    stage: str
    error_type: str
    http_status: int | None
    tracking_id: str | None
    details: str


@dataclass
class ChangeEntry:
    user_email: str
    stage: str
    status: str
    before: Any
    after: Any
    details: str
