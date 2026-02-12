from __future__ import annotations

from .common import ModuleResult, as_list, call_with_supported_kwargs, details_keys, model_to_dict


def run_group_members(api) -> ModuleResult:
    groups = [model_to_dict(g) for g in as_list(api.groups.list())]
    rows: list[dict] = []
    for group in groups:
        gid = group.get('id') or group.get('group_id')
        if not gid:
            continue
        members = [model_to_dict(m) for m in as_list(api.groups.members(group_id=gid))]
        for member in members:
            rows.append({'group_id': gid, 'person_id': member.get('id') or member.get('member_id') or ''})
    return ModuleResult(module='group_members', method='groups.members', rows=rows, count=len(rows), raw_keys=[])


def run_schedules(api) -> ModuleResult:
    locations = [model_to_dict(l) for l in as_list(api.locations.list())]
    rows: list[dict] = []
    sample_keys: list[str] = []
    for loc in locations:
        loc_id = loc.get('id') or loc.get('location_id')
        if not loc_id:
            continue
        for schedule_type in ('businessHours', 'holidays'):
            try:
                scheds = as_list(api.telephony.location_schedules.list(obj_id=loc_id, schedule_type=schedule_type))
            except AttributeError:
                scheds = as_list(api.telephony.location.schedules.list(obj_id=loc_id, schedule_type=schedule_type))
            for sched in scheds:
                item = model_to_dict(sched)
                rows.append({
                    'id': item.get('id', ''),
                    'name': item.get('name', ''),
                    'location_id': loc_id,
                    'extension': '',
                    'phone_number': '',
                    'raw_keys': '',
                })
    if rows:
        first = rows[0]
        sid = first.get('id')
        if sid:
            try:
                detail = api.telephony.location_schedules.details(obj_id=first['location_id'], schedule_type='businessHours',
                                                                 schedule_id=sid)
            except AttributeError:
                detail = api.telephony.location.schedules.details(obj_id=first['location_id'], schedule_type='businessHours',
                                                                  schedule_id=sid)
            sample_keys = details_keys(detail)
    raw_keys = ','.join(sample_keys)
    for row in rows:
        row['raw_keys'] = raw_keys
    return ModuleResult(module='schedules', method='telephony.location.schedules.list', rows=rows, count=len(rows),
                        raw_keys=sample_keys)


def run_pstn_locations(api) -> ModuleResult:
    tlocs = [model_to_dict(l) for l in as_list(api.telephony.location.list())]
    rows: list[dict] = []
    for loc in tlocs:
        loc_id = loc.get('id')
        if not loc_id:
            continue
        options = as_list(call_with_supported_kwargs(api.telephony.pstn.list, location_id=loc_id))
        for opt in options:
            item = model_to_dict(opt)
            rows.append({
                'id': item.get('id', loc_id),
                'name': item.get('name', item.get('pstn_provider', 'pstn')),
                'location_id': loc_id,
                'extension': '',
                'phone_number': '',
                'raw_keys': ','.join(sorted(item.keys())),
            })
    return ModuleResult(module='pstn_locations', method='telephony.pstn.list', rows=rows, count=len(rows), raw_keys=[])
