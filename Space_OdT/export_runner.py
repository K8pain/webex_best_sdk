from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .io.artifact_paths import ensure_dirs
from .io.csv_writer import write_csv
from .io.json_writer import write_json
from .modules.catalog import MODULE_SPECS, run_spec
from .modules.v1_manifest import STANDARD_COLUMNS, V1_ARTIFACT_SPECS, run_artifact
from .status import StatusRecord, StatusRecorder, classify_exception, timed_call


EXPORT_COLUMNS = {
    'people': ['person_id', 'email', 'display_name', 'status', 'roles', 'licenses', 'location_id'],
    'groups': ['group_id', 'name'],
    'locations': ['location_id', 'name', 'org_id', 'timezone'],
    'licenses': ['license_id', 'sku_or_name'],
    'status': ['module', 'method', 'result', 'http_status', 'error', 'count', 'elapsed_ms'],
}


def _columns_for_module(module_name: str) -> list[str]:
    return EXPORT_COLUMNS.get(module_name, STANDARD_COLUMNS)


def _write_module_exports(exports_dir: Path, module_name: str, rows: list[dict]) -> None:
    write_json(exports_dir / f'{module_name}.json', rows)
    write_csv(exports_dir / f'{module_name}.csv', rows, _columns_for_module(module_name))


def _empty_module(exports_dir: Path, module_name: str) -> None:
    _write_module_exports(exports_dir, module_name, [])


def _write_cache_if_enabled(settings: Settings, cache_entities: dict) -> None:
    if not settings.write_cache:
        return
    payload = {
        'meta': {
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'schema_version': 'v1',
        },
        'entities': cache_entities,
    }
    write_json(settings.out_dir / 'cache.json', payload)


def _write_report_if_enabled(settings: Settings, status_rows: list[dict], module_counts: dict[str, int]) -> Path | None:
    if not settings.write_report:
        return None
    report_file = settings.out_dir / 'report' / 'index.html'
    rows_html = ''.join(
        f"<tr><td>{row['module']}</td><td><code>{row['method']}</code></td><td><span class='badge {row['result']}'>{row['result']}</span></td><td>{row['count']}</td><td>{row['error']}</td></tr>"
        for row in status_rows
    )
    total_modules = len(module_counts)
    ok_modules = sum(1 for row in status_rows if row['result'] == 'ok')
    error_modules = total_modules - ok_modules
    modules_list = ''.join(
        f"<li><span>{name}</span><strong>{count}</strong></li>"
        for name, count in sorted(module_counts.items())
    )
    html = f"""
<!doctype html>
<html><head><meta charset='utf-8'><title>Space_OdT Export Report</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: Inter, Segoe UI, Arial, sans-serif; margin: 0; background:#f6f8fc; color:#1f2a44; }}
.wrap {{ max-width: 1280px; margin: 0 auto; padding: 24px; }}
.top {{ display:flex; gap: 12px; margin: 14px 0 20px; flex-wrap: wrap; }}
.chip {{ background: #fff; border:1px solid #dce2ef; border-radius: 999px; padding: 8px 14px; }}
.layout {{ display:grid; grid-template-columns: 340px 1fr; gap:16px; align-items: start; }}
.card {{ background:#fff; border:1px solid #dce2ef; border-radius:12px; padding:14px; box-shadow:0 1px 2px rgba(16,24,40,.04); }}
h1 {{ margin:0; font-size: 28px; }}
h2 {{ margin:0 0 10px; font-size: 18px; }}
ul {{ list-style:none; padding:0; margin:0; max-height: 70vh; overflow:auto; }}
li {{ display:flex; justify-content:space-between; border-bottom:1px dashed #e8ecf5; padding:7px 0; gap:8px; }}
li:last-child {{ border-bottom:0; }}
table {{ border-collapse: collapse; width:100%; font-size:14px; }}
thead th {{ position: sticky; top: 0; background: #f9fbff; }}
th,td {{ border-bottom:1px solid #edf1f7; padding:8px; text-align:left; vertical-align: top; }}
.badge {{ border-radius:999px; padding:2px 10px; font-size:12px; font-weight:600; text-transform: uppercase; }}
.ok {{ background:#e9f9ef; color:#1f7a44; }}
.error,.forbidden,.not_found {{ background:#feecef; color:#b42318; }}
code {{ background:#f3f6fd; padding:1px 4px; border-radius:4px; }}
</style></head>
<body>
<div class='wrap'>
<h1>Space_OdT Export Report</h1>
<div class='top'>
  <div class='chip'>Módulos: <strong>{total_modules}</strong></div>
  <div class='chip'>OK: <strong>{ok_modules}</strong></div>
  <div class='chip'>Con error: <strong>{error_modules}</strong></div>
</div>
</div>
<div class='layout'>
  <aside class='card'><h2>Inventario (misma plana)</h2><ul>{modules_list}</ul></aside>
  <section class='card'><h2>Estado por método</h2><table><thead><tr><th>Module</th><th>Method</th><th>Result</th><th>Count</th><th>Error</th></tr></thead><tbody>{rows_html}</tbody></table></section>
</div>
</div>
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

    for spec in V1_ARTIFACT_SPECS:
        if spec.module not in settings.enabled_modules:
            continue
        try:
            result, elapsed = timed_call(run_artifact, api, spec, cache_entities)
            _write_module_exports(exports_dir, result.module, result.rows)
            cache_entities[result.module] = result.rows
            module_counts[result.module] = result.count
            recorder.add(StatusRecord(result.module, result.method, 'ok', None, '', result.count, elapsed))
        except Exception as exc:
            err, status, msg = classify_exception(exc)
            _empty_module(exports_dir, spec.module)
            recorder.add(StatusRecord(spec.module, spec.method_path, err, status, msg, 0, 0))
            cache_entities[spec.module] = []
            module_counts[spec.module] = 0

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
