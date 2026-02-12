from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .models import ChangeEntry, FailureEntry, InputRecord


def load_policy(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _normalize_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    value = raw.strip().lower()
    if value == '':
        return None
    return value in {'1', 'true', 'yes', 'y', 'on'}


def _normalize_phone(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if value.startswith('+') and value[1:].isdigit():
        return value
    if value.isdigit():
        return f'+{value}'
    raise ValueError(f'invalid phone_number format: {raw}')


def load_input_records(path: Path) -> list[InputRecord]:
    with path.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    required = {'user_email', 'calling_license_id'}
    if not required.issubset(set(reader.fieldnames or [])):
        missing = ', '.join(sorted(required - set(reader.fieldnames or [])))
        raise ValueError(f'missing required CSV columns: {missing}')

    results: list[InputRecord] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        email = (row.get('user_email') or '').strip().lower()
        if not email:
            raise ValueError(f'row {row_number}: user_email is required')
        if email in seen:
            raise ValueError(f'row {row_number}: duplicated user_email {email}')
        seen.add(email)

        calling_license_id = (row.get('calling_license_id') or '').strip()
        if not calling_license_id:
            raise ValueError(f'row {row_number}: calling_license_id is required')

        location_id = (row.get('location_id') or '').strip()
        location_name = (row.get('location_name') or '').strip()
        if not location_id and not location_name:
            raise ValueError(f'row {row_number}: location_id or location_name is required')

        extension = (row.get('extension') or '').strip() or None
        phone_number = _normalize_phone(row.get('phone_number'))
        if not extension and not phone_number:
            raise ValueError(f'row {row_number}: extension or phone_number is required')

        normalized: dict[str, Any] = {}
        for key, value in row.items():
            if value is None:
                normalized[key] = None
                continue
            stripped = value.strip()
            normalized[key] = _normalize_bool(stripped) if key.endswith('_enabled') else (stripped or None)

        normalized['phone_number'] = phone_number
        results.append(
            InputRecord(
                row_number=row_number,
                user_email=email,
                calling_license_id=calling_license_id,
                location_id=location_id or location_name,
                extension=extension,
                phone_number=phone_number,
                payload=normalized,
            )
        )
    return results


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == '.csv':
        with path.open('r', encoding='utf-8', newline='') as handle:
            return list(csv.DictReader(handle))
    data = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get('items'), list):
        return data['items']
    raise ValueError(f'unsupported override format in {path}')


def load_stage_overrides(path: Path) -> dict[str, dict[str, Any]]:
    rows = _read_rows(path)
    overrides: dict[str, dict[str, Any]] = {}
    for row in rows:
        email = str(row.get('user_email') or '').strip().lower()
        if not email:
            continue
        overrides[email] = {k: v for k, v in row.items() if k != 'user_email'}
    return overrides


def load_v1_maps(v1_inventory_dir: Path) -> dict[str, dict[str, str]]:
    def read_inventory(name: str) -> list[dict[str, Any]]:
        for ext in ('csv', 'json'):
            p = v1_inventory_dir / f'{name}.{ext}'
            if p.exists():
                return _read_rows(p)
        return []

    people = read_inventory('people')
    locations = read_inventory('locations')
    call_queues = read_inventory('call_queues')

    return {
        'email_to_person_id': {
            (r.get('email') or '').strip().lower(): (r.get('person_id') or r.get('id') or '').strip()
            for r in people if (r.get('email') and (r.get('person_id') or r.get('id')))
        },
        'location_name_to_id': {
            (r.get('name') or '').strip().lower(): (r.get('location_id') or r.get('id') or '').strip()
            for r in locations if (r.get('name') and (r.get('location_id') or r.get('id')))
        },
        'queue_name_to_id': {
            (r.get('name') or '').strip().lower(): (r.get('id') or r.get('queue_id') or '').strip()
            for r in call_queues if (r.get('name') and (r.get('id') or r.get('queue_id')))
        },
    }


def load_run_state(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {
        'run_id': '',
        'started_at': '',
        'completed_count': 0,
        'failed_count': 0,
        'record_results': {},
        'stage_decisions': {},
    }


def save_run_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True), encoding='utf-8')


def append_failures(path: Path, failures: list[FailureEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open('a', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        if not exists:
            writer.writerow(['user_email', 'stage', 'error_type', 'http_status', 'tracking_id', 'details'])
        for failure in failures:
            writer.writerow([failure.user_email, failure.stage, failure.error_type, failure.http_status, failure.tracking_id, failure.details])


def write_change_log(path: Path, changes: list[ChangeEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        for change in changes:
            handle.write(json.dumps(change.__dict__, ensure_ascii=False, default=str) + '\n')


def write_html_report(path: Path, *, run_id: str, changes: list[ChangeEntry], failures: list[FailureEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for c in changes:
        rows.append(
            f"<tr><td>{c.user_email}</td><td>{c.stage}</td><td>{c.status}</td>"
            f"<td><pre>{json.dumps(c.before, ensure_ascii=False, default=str)}</pre></td>"
            f"<td><pre>{json.dumps(c.after, ensure_ascii=False, default=str)}</pre></td>"
            f"<td>{c.details}</td></tr>"
        )
    failure_rows = ''.join(
        f"<li>{f.user_email} | {f.stage} | {f.error_type} | {f.details}</li>" for f in failures
    )
    html = (
        '<html><head><meta charset="utf-8"><title>V2 Bulk Report</title></head><body>'
        f'<h1>V2 Bulk Report</h1><p>run_id={run_id}</p>'
        '<h2>Changes (before/after)</h2>'
        '<table border="1" cellspacing="0" cellpadding="4">'
        '<tr><th>User</th><th>Stage</th><th>Status</th><th>Before</th><th>After</th><th>Details</th></tr>'
        + ''.join(rows) + '</table>'
        + '<h2>Failures</h2><ul>' + failure_rows + '</ul></body></html>'
    )
    path.write_text(html, encoding='utf-8')
