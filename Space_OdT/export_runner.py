from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .io.artifact_paths import ensure_dirs
from .io.csv_writer import write_csv
from .io.json_writer import write_json
from .modules.catalog import CALLING_COLUMNS, MODULE_SPECS, run_spec
from .modules.special_modules import run_group_members, run_pstn_locations, run_schedules
from .status import StatusRecord, StatusRecorder, classify_exception, timed_call


EXPORT_COLUMNS = {
    'people': ['person_id', 'email', 'display_name', 'status', 'roles', 'licenses', 'location_id'],
    'groups': ['group_id', 'name'],
    'group_members': ['group_id', 'person_id'],
    'locations': ['location_id', 'name', 'org_id', 'timezone'],
    'licenses': ['license_id', 'sku_or_name'],
    'call_queues': CALLING_COLUMNS,
    'hunt_groups': CALLING_COLUMNS,
    'auto_attendants': CALLING_COLUMNS,
    'virtual_lines': CALLING_COLUMNS,
    'virtual_extensions': CALLING_COLUMNS,
    'schedules': CALLING_COLUMNS,
    'pstn_locations': CALLING_COLUMNS,
    'devices': CALLING_COLUMNS,
    'workspaces': CALLING_COLUMNS,
    'status': ['module', 'method', 'result', 'http_status', 'error', 'count', 'elapsed_ms'],
}


def _write_module_exports(exports_dir: Path, module_name: str, rows: list[dict]) -> None:
    write_json(exports_dir / f'{module_name}.json', rows)
    write_csv(exports_dir / f'{module_name}.csv', rows, EXPORT_COLUMNS[module_name])


def _empty_module(exports_dir: Path, module_name: str) -> None:
    _write_module_exports(exports_dir, module_name, [])


def _write_cache_if_enabled(settings: Settings, cache_entities: dict) -> None:
    if not settings.write_cache:
        return
    payload = {
        'meta': {
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'schema_version': 'v0',
        },
        'entities': cache_entities,
    }
    write_json(settings.out_dir / 'cache.json', payload)


def _write_report_if_enabled(settings: Settings, status_rows: list[dict], module_counts: dict[str, int]) -> Path | None:
    if not settings.write_report:
        return None
    report_file = settings.out_dir / 'report' / 'index.html'
    rows_html = ''.join(
        f"<tr><td>{row['module']}</td><td>{row['result']}</td><td>{row['count']}</td><td>{row['error']}</td></tr>"
        for row in status_rows
    )
    counts_html = ''.join(f'<li>{name}: {count}</li>' for name, count in module_counts.items())
    html = f"""
<!doctype html>
<html><head><meta charset='utf-8'><title>Space_OdT Export Report</title></head>
<body>
<h1>Space_OdT Export Report</h1>
<ul>{counts_html}</ul>
<table border='1'><thead><tr><th>Module</th><th>Result</th><th>Count</th><th>Error</th></tr></thead><tbody>{rows_html}</tbody></table>
</body></html>
""".strip()
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(html, encoding='utf-8')
    return report_file


def run_exports(api, settings: Settings) -> dict:
    paths = ensure_dirs(settings.out_dir)
    exports_dir = paths['exports']

    recorder = StatusRecorder()
    cache_entities: dict[str, list[dict]] = {}
    module_counts: dict[str, int] = {}

    for spec in MODULE_SPECS:
        if spec.name not in settings.enabled_modules:
            continue
        try:
            result, elapsed = timed_call(run_spec, api, spec)
            _write_module_exports(exports_dir, result.module, result.rows)
            cache_entities[result.module] = result.rows
            module_counts[result.module] = result.count
            recorder.add(StatusRecord(spec.name, spec.list_path, 'ok', None, '', result.count, elapsed))
        except Exception as exc:
            err, status, msg = classify_exception(exc)
            _empty_module(exports_dir, spec.name)
            recorder.add(StatusRecord(spec.name, spec.list_path, err, status, msg, 0, 0))
            cache_entities[spec.name] = []
            module_counts[spec.name] = 0

    if settings.include_group_members:
        try:
            result, elapsed = timed_call(run_group_members, api)
            _write_module_exports(exports_dir, result.module, result.rows)
            cache_entities[result.module] = result.rows
            module_counts[result.module] = result.count
            recorder.add(StatusRecord(result.module, result.method, 'ok', None, '', result.count, elapsed))
        except Exception as exc:
            err, status, msg = classify_exception(exc)
            _empty_module(exports_dir, 'group_members')
            recorder.add(StatusRecord('group_members', 'groups.members', err, status, msg, 0, 0))
            cache_entities['group_members'] = []

    for special_name, fn in [('schedules', run_schedules), ('pstn_locations', run_pstn_locations)]:
        if special_name not in settings.enabled_modules:
            continue
        try:
            result, elapsed = timed_call(fn, api)
            _write_module_exports(exports_dir, result.module, result.rows)
            cache_entities[result.module] = result.rows
            module_counts[result.module] = result.count
            recorder.add(StatusRecord(result.module, result.method, 'ok', None, '', result.count, elapsed))
        except Exception as exc:
            err, status, msg = classify_exception(exc)
            _empty_module(exports_dir, special_name)
            recorder.add(StatusRecord(special_name, special_name, err, status, msg, 0, 0))
            cache_entities[special_name] = []
            module_counts[special_name] = 0

    status_rows = [asdict(r) for r in recorder.records]
    write_csv(exports_dir / 'status.csv', status_rows, EXPORT_COLUMNS['status'])
    write_json(exports_dir / 'status.json', status_rows)

    _write_cache_if_enabled(settings, cache_entities)
    report_path = _write_report_if_enabled(settings, status_rows, module_counts)

    return {
        'out_dir': str(settings.out_dir),
        'exports_dir': str(exports_dir),
        'status_count': len(status_rows),
        'module_counts': module_counts,
        'report_path': str(report_path) if report_path else '',
    }
