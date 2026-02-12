from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import product
from typing import Any

from .common import ModuleResult, as_list, call_with_supported_kwargs, model_to_dict, resolve_attr


STANDARD_COLUMNS = [
    'id',
    'name',
    'location_id',
    'person_id',
    'workspace_id',
    'license_id',
    'virtual_line_id',
    'group_id',
    'source_method',
    'raw_keys',
    'raw_json',
]


@dataclass(frozen=True)
class ParamSource:
    name: str
    module: str
    field: str


@dataclass(frozen=True)
class ArtifactSpec:
    module: str
    method_path: str
    static_kwargs: dict[str, Any]
    param_sources: tuple[ParamSource, ...] = ()


def _id_values(cache: dict[str, list[dict]], source: ParamSource) -> list[Any]:
    rows = cache.get(source.module, [])
    values = [r.get(source.field) for r in rows if r.get(source.field)]
    uniq: list[Any] = []
    seen = set()
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        uniq.append(v)
    return uniq


def _iter_kwargs(cache: dict[str, list[dict]], spec: ArtifactSpec) -> list[dict[str, Any]]:
    if not spec.param_sources:
        return [dict(spec.static_kwargs)]
    value_lists = [_id_values(cache, src) for src in spec.param_sources]
    if any(not vals for vals in value_lists):
        return []
    keys = [s.name for s in spec.param_sources]
    out: list[dict[str, Any]] = []
    for combo in product(*value_lists):
        kwargs = dict(spec.static_kwargs)
        kwargs.update(dict(zip(keys, combo)))
        out.append(kwargs)
    return out


def _row_from_item(item: dict, method_path: str, kwargs: dict[str, Any]) -> dict:
    row = {k: item.get(k, '') for k in STANDARD_COLUMNS}
    for k in ('location_id', 'person_id', 'workspace_id', 'license_id', 'virtual_line_id', 'group_id', 'id', 'name'):
        if not row.get(k) and kwargs.get(k):
            row[k] = kwargs[k]
    for k, v in kwargs.items():
        if k.endswith('_id') and k not in row:
            row[k] = v
    row['source_method'] = method_path
    row['raw_keys'] = ','.join(sorted(item.keys()))
    row['raw_json'] = json.dumps(item, ensure_ascii=False, sort_keys=True)
    return row


def run_artifact(api, spec: ArtifactSpec, cache: dict[str, list[dict]]) -> ModuleResult:
    method = resolve_attr(api, spec.method_path)
    rows: list[dict] = []
    for kwargs in _iter_kwargs(cache, spec):
        payload = call_with_supported_kwargs(method, **kwargs)
        items = [model_to_dict(i) for i in as_list(payload)]
        if not items and isinstance(payload, object):
            maybe = model_to_dict(payload)
            if maybe:
                items = [maybe]
        for item in items:
            rows.append(_row_from_item(item, spec.method_path, kwargs))
    return ModuleResult(module=spec.module, method=spec.method_path, rows=rows, count=len(rows), raw_keys=[])


V1_ARTIFACT_SPECS: list[ArtifactSpec] = [
    ArtifactSpec('calling_locations', 'telephony.locations.list', {}),
    ArtifactSpec('calling_locations_details', 'telephony.locations.details', {}, (ParamSource('location_id', 'calling_locations', 'id'),)),
    ArtifactSpec('group_members', 'groups.members', {}, (ParamSource('group_id', 'groups', 'group_id'),)),
    ArtifactSpec('license_assigned_users', 'licenses.assigned_users', {}, (ParamSource('license_id', 'licenses', 'license_id'),)),
    ArtifactSpec('workspace_capabilities', 'workspaces.capabilities', {}, (ParamSource('workspace_id', 'workspaces', 'id'),)),

    ArtifactSpec('auto_attendants', 'telephony.auto_attendant.list', {}),
    ArtifactSpec('auto_attendant_details', 'telephony.auto_attendant.details', {},
                 (ParamSource('location_id', 'auto_attendants', 'location_id'), ParamSource('auto_attendant_id', 'auto_attendants', 'id'))),
    ArtifactSpec('auto_attendant_announcement_files', 'telephony.auto_attendant.list_announcement_files', {},
                 (ParamSource('location_id', 'auto_attendants', 'location_id'), ParamSource('auto_attendant_id', 'auto_attendants', 'id'))),
    ArtifactSpec('auto_attendant_forwarding', 'telephony.auto_attendant.forwarding.settings', {},
                 (ParamSource('location_id', 'auto_attendants', 'location_id'), ParamSource('auto_attendant_id', 'auto_attendants', 'id'))),

    ArtifactSpec('hunt_groups', 'telephony.huntgroup.list', {}),
    ArtifactSpec('hunt_group_details', 'telephony.huntgroup.details', {},
                 (ParamSource('location_id', 'hunt_groups', 'location_id'), ParamSource('huntgroup_id', 'hunt_groups', 'id'))),
    ArtifactSpec('hunt_group_forwarding', 'telephony.huntgroup.forwarding.settings', {},
                 (ParamSource('location_id', 'hunt_groups', 'location_id'), ParamSource('huntgroup_id', 'hunt_groups', 'id'))),

    ArtifactSpec('call_queues', 'telephony.callqueue.list', {}),
    ArtifactSpec('call_queue_details', 'telephony.callqueue.details', {},
                 (ParamSource('location_id', 'call_queues', 'location_id'), ParamSource('queue_id', 'call_queues', 'id'))),
    ArtifactSpec('call_queue_settings', 'telephony.callqueue.get_call_queue_settings', {},
                 (ParamSource('location_id', 'call_queues', 'location_id'), ParamSource('queue_id', 'call_queues', 'id'))),
    ArtifactSpec('call_queue_agents', 'telephony.callqueue.agents.list', {},
                 (ParamSource('location_id', 'call_queues', 'location_id'), ParamSource('queue_id', 'call_queues', 'id'))),
    ArtifactSpec('call_queue_forwarding', 'telephony.callqueue.forwarding.settings', {},
                 (ParamSource('location_id', 'call_queues', 'location_id'), ParamSource('queue_id', 'call_queues', 'id'))),

    ArtifactSpec('virtual_lines', 'telephony.virtual_lines.list', {}),
    ArtifactSpec('virtual_line_details', 'telephony.virtual_lines.details', {},
                 (ParamSource('virtual_line_id', 'virtual_lines', 'id'),)),
    ArtifactSpec('virtual_line_assigned_devices', 'telephony.virtual_lines.assigned_devices', {},
                 (ParamSource('virtual_line_id', 'virtual_lines', 'id'),)),

    ArtifactSpec('virtual_extensions', 'telephony.virtual_extensions.list_extensions', {}),
    ArtifactSpec('virtual_extension_details', 'telephony.virtual_extensions.details_extension', {},
                 (ParamSource('location_id', 'virtual_extensions', 'location_id'), ParamSource('extension_id', 'virtual_extensions', 'id'))),
    ArtifactSpec('virtual_extension_ranges', 'telephony.virtual_extensions.list_range', {}),
    ArtifactSpec('virtual_extension_range_details', 'telephony.virtual_extensions.details_range', {},
                 (ParamSource('location_id', 'virtual_extension_ranges', 'location_id'), ParamSource('range_id', 'virtual_extension_ranges', 'id'))),

    ArtifactSpec('person_numbers', 'person_settings.numbers.read', {}, (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('person_permissions_in', 'person_settings.permissions_in.read', {}, (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('person_permissions_out', 'person_settings.permissions_out.read', {}, (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('person_out_access_codes', 'person_settings.permissions_out.access_codes.read', {}, (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('person_out_digit_patterns', 'person_settings.permissions_out.digit_patterns.get_digit_patterns', {}, (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('person_transfer_numbers', 'person_settings.permissions_out.transfer_numbers.read', {}, (ParamSource('person_id', 'people', 'person_id'),)),

    ArtifactSpec('workspace_permissions_in', 'workspace_settings.permissions_in.read', {}, (ParamSource('workspace_id', 'workspaces', 'id'),)),
    ArtifactSpec('workspace_permissions_out', 'workspace_settings.permissions_out.read', {}, (ParamSource('workspace_id', 'workspaces', 'id'),)),
    ArtifactSpec('workspace_devices', 'workspace_settings.devices.list', {}, (ParamSource('workspace_id', 'workspaces', 'id'),)),

    ArtifactSpec('person_available_numbers_available', 'person_settings.available_numbers.available', {}, (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('person_available_numbers_primary', 'person_settings.available_numbers.primary', {}, (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('person_available_numbers_secondary', 'person_settings.available_numbers.secondary', {}, (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('person_available_numbers_call_forward', 'person_settings.available_numbers.call_forward', {}, (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('person_available_numbers_call_intercept', 'person_settings.available_numbers.call_intercept', {}, (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('person_available_numbers_ecbn', 'person_settings.available_numbers.ecbn', {}, (ParamSource('person_id', 'people', 'person_id'),)),
    ArtifactSpec('person_available_numbers_fax_message', 'person_settings.available_numbers.fax_message', {}, (ParamSource('person_id', 'people', 'person_id'),)),

    ArtifactSpec('virtual_line_available_numbers_available', 'telephony.virtual_lines.available_numbers.available', {}, (ParamSource('virtual_line_id', 'virtual_lines', 'id'),)),
    ArtifactSpec('virtual_line_available_numbers_primary', 'telephony.virtual_lines.available_numbers.primary', {}, (ParamSource('virtual_line_id', 'virtual_lines', 'id'),)),
    ArtifactSpec('virtual_line_available_numbers_secondary', 'telephony.virtual_lines.available_numbers.secondary', {}, (ParamSource('virtual_line_id', 'virtual_lines', 'id'),)),

    ArtifactSpec('workspace_available_numbers_available', 'workspace_settings.available_numbers.available', {}, (ParamSource('workspace_id', 'workspaces', 'id'),)),
    ArtifactSpec('workspace_available_numbers_primary', 'workspace_settings.available_numbers.primary', {}, (ParamSource('workspace_id', 'workspaces', 'id'),)),
    ArtifactSpec('workspace_available_numbers_secondary', 'workspace_settings.available_numbers.secondary', {}, (ParamSource('workspace_id', 'workspaces', 'id'),)),
]
