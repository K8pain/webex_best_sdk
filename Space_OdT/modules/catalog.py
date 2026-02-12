from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .common import ModuleResult, as_list, call_with_supported_kwargs, details_keys, model_to_dict, resolve_attr


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    list_path: str
    detail_path: str | None
    detail_id_field: str
    static_list_kwargs: dict[str, Any]
    to_row: Callable[[dict], dict]
    detail_kwargs_builder: Callable[[dict], dict]


CALLING_COLUMNS = ['id', 'name', 'location_id', 'extension', 'phone_number', 'raw_keys']


def _value(d: dict, *keys: str):
    for k in keys:
        if k in d and d.get(k) not in (None, ''):
            return d.get(k)
    return ''


def default_calling_row(item: dict) -> dict:
    phone = _value(item, 'phone_number', 'phoneNumber')
    extension = _value(item, 'extension', 'extensionNumber')
    return {
        'id': _value(item, 'id'),
        'name': _value(item, 'name', 'first_name'),
        'location_id': _value(item, 'location_id', 'locationId'),
        'extension': extension,
        'phone_number': phone,
        'raw_keys': '',
    }


def people_row(item: dict) -> dict:
    calling_data = item.get('calling_data') or item.get('callingData') or {}
    return {
        'person_id': _value(item, 'person_id', 'id'),
        'email': (item.get('emails') or [''])[0] if isinstance(item.get('emails'), list) else item.get('email', ''),
        'display_name': _value(item, 'display_name', 'displayName'),
        'status': _value(item, 'status'),
        'roles': ';'.join(item.get('roles', []) or []),
        'licenses': ';'.join(item.get('licenses', []) or []),
        'location_id': _value(calling_data, 'location_id', 'locationId') if isinstance(calling_data, dict) else '',
    }


def groups_row(item: dict) -> dict:
    return {'group_id': _value(item, 'group_id', 'id'), 'name': _value(item, 'display_name', 'displayName') or _value(item, 'name')}


def locations_row(item: dict) -> dict:
    return {
        'location_id': _value(item, 'location_id', 'id'),
        'name': _value(item, 'name'),
        'org_id': _value(item, 'org_id', 'orgId'),
        'timezone': _value(item, 'time_zone', 'timeZone'),
    }


def licenses_row(item: dict) -> dict:
    return {'license_id': _value(item, 'license_id', 'id'), 'sku_or_name': _value(item, 'name', 'display_name', 'displayName')}


MODULE_SPECS: list[ModuleSpec] = [
    ModuleSpec('people', 'people.list', 'people.details', 'person_id', {'calling_data': True}, people_row,
               lambda row: {'person_id': row.get('person_id'), 'calling_data': True}),
    ModuleSpec('groups', 'groups.list', 'groups.details', 'group_id', {}, groups_row,
               lambda row: {'group_id': row.get('group_id')}),
    ModuleSpec('locations', 'locations.list', 'locations.details', 'location_id', {}, locations_row,
               lambda row: {'location_id': row.get('location_id')}),
    ModuleSpec('licenses', 'licenses.list', 'licenses.details', 'license_id', {}, licenses_row,
               lambda row: {'license_id': row.get('license_id')}),
    ModuleSpec('call_queues', 'telephony.callqueue.list', 'telephony.callqueue.details', 'id', {}, default_calling_row,
               lambda row: {'location_id': row.get('location_id'), 'queue_id': row.get('id')}),
    ModuleSpec('hunt_groups', 'telephony.huntgroup.list', 'telephony.huntgroup.details', 'id', {}, default_calling_row,
               lambda row: {'location_id': row.get('location_id'), 'huntgroup_id': row.get('id')}),
    ModuleSpec('auto_attendants', 'telephony.auto_attendant.list', 'telephony.auto_attendant.details', 'id', {}, default_calling_row,
               lambda row: {'location_id': row.get('location_id'), 'auto_attendant_id': row.get('id')}),
    ModuleSpec('virtual_lines', 'telephony.virtual_lines.list', 'telephony.virtual_lines.details', 'id', {}, default_calling_row,
               lambda row: {'virtual_line_id': row.get('id')}),
    ModuleSpec('virtual_extensions', 'telephony.virtual_extensions.list_range', None, 'id', {}, default_calling_row,
               lambda row: {}),
    ModuleSpec('devices', 'devices.list', 'devices.details', 'id', {}, default_calling_row,
               lambda row: {'device_id': row.get('id')}),
    ModuleSpec('workspaces', 'workspaces.list', 'workspaces.details', 'id', {}, default_calling_row,
               lambda row: {'workspace_id': row.get('id')}),
]


def run_spec(api, spec: ModuleSpec) -> ModuleResult:
    list_fn = resolve_attr(api, spec.list_path)
    raw = call_with_supported_kwargs(list_fn, **spec.static_list_kwargs)
    items = [model_to_dict(v) for v in as_list(raw)]
    rows = [spec.to_row(i) for i in items]
    keys: list[str] = []
    if rows and spec.detail_path:
        detail_fn = resolve_attr(api, spec.detail_path)
        detail_kwargs = spec.detail_kwargs_builder(rows[0])
        detail_obj = call_with_supported_kwargs(detail_fn, **detail_kwargs)
        keys = details_keys(detail_obj)
    for row in rows:
        if 'raw_keys' in row:
            row['raw_keys'] = ','.join(keys)
    return ModuleResult(module=spec.name, method=spec.list_path, rows=rows, count=len(rows), raw_keys=keys)
