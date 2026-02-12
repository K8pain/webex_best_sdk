from __future__ import annotations

from dataclasses import asdict
from html import escape
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
    base_modules = {'people', 'groups', 'locations', 'licenses', 'workspaces', 'calling_locations'}
    artifact_modules = sorted(name for name in module_counts if name not in base_modules)

    base_list = ''.join(
        f"<li><span>{escape(name)}</span><strong>{module_counts.get(name, 0)}</strong></li>"
        for name in sorted(base_modules)
    )
    artifact_list = ''.join(
        f"<li><span>{escape(name)}</span><strong>{module_counts[name]}</strong></li>"
        for name in artifact_modules
    )

    ok_count = sum(1 for row in status_rows if row.get('result') == 'ok')
    not_found_count = sum(1 for row in status_rows if row.get('result') == 'not_found')
    error_count = sum(1 for row in status_rows if row.get('result') == 'error')

    rows_html = ''.join(
        (
            '<tr>'
            f"<td>{escape(str(row.get('module', '')))}</td>"
            f"<td><code>{escape(str(row.get('method', '')))}</code></td>"
            f"<td><span class='badge badge-{escape(str(row.get('result', 'unknown')))}'>{escape(str(row.get('result', '')))}</span></td>"
            f"<td>{escape(str(row.get('count', 0)))}</td>"
            f"<td class='error-cell'>{escape(str(row.get('error', '')))}</td>"
            '</tr>'
        )
        for row in status_rows
    )

    html = f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Space_OdT Export Report</title>
  <style>
    :root {{
      --bg: #0b1020;
      --surface: #121a31;
      --surface-soft: #192344;
      --line: #2a3763;
      --text: #e6ebff;
      --muted: #a9b6dd;
      --ok: #2ecc71;
      --warn: #f1c40f;
      --err: #ff6b6b;
      --accent: #6aa8ff;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      background: radial-gradient(circle at top, #1a2550, var(--bg) 45%);
      color: var(--text);
      padding: 24px;
    }}

    .container {{ max-width: 1280px; margin: 0 auto; }}
    .header {{ margin-bottom: 20px; }}
    h1 {{ margin: 0 0 6px; font-size: 1.8rem; }}
    .subtitle {{ color: var(--muted); margin: 0; }}

    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin: 20px 0;
    }}

    .metric {{
      background: linear-gradient(145deg, var(--surface), var(--surface-soft));
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
    }}

    .metric-label {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 8px; }}
    .metric-value {{ font-size: 1.5rem; font-weight: 700; }}

    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}

    .card {{
      background: linear-gradient(180deg, var(--surface), #121a2b);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
    }}

    .card h2 {{ margin: 0 0 10px; font-size: 1.05rem; }}
    ul {{ list-style: none; margin: 0; padding: 0; max-height: 280px; overflow: auto; }}
    li {{ display: flex; justify-content: space-between; border-bottom: 1px dashed #31426f; padding: 6px 0; gap: 8px; }}
    li:last-child {{ border-bottom: none; }}
    li span {{ color: var(--muted); font-size: 0.93rem; }}
    li strong {{ color: var(--text); }}

    .table-wrap {{
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--surface);
    }}

    table {{ width: 100%; border-collapse: collapse; min-width: 860px; }}
    thead th {{
      position: sticky;
      top: 0;
      background: #1d2a4a;
      color: var(--text);
      text-align: left;
      font-weight: 600;
      border-bottom: 1px solid var(--line);
      padding: 10px;
    }}

    tbody td {{ border-bottom: 1px solid #24345f; padding: 10px; vertical-align: top; }}
    tbody tr:hover {{ background: rgba(106, 168, 255, 0.08); }}
    code {{ color: #c7d5ff; font-size: 0.9em; }}

    .badge {{
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      border: 1px solid transparent;
    }}
    .badge-ok {{ color: #a7f3c2; background: rgba(46, 204, 113, 0.15); border-color: rgba(46, 204, 113, 0.35); }}
    .badge-not_found {{ color: #ffe8a3; background: rgba(241, 196, 15, 0.16); border-color: rgba(241, 196, 15, 0.35); }}
    .badge-error {{ color: #ffc4c4; background: rgba(255, 107, 107, 0.16); border-color: rgba(255, 107, 107, 0.35); }}
    .error-cell {{ color: #ffccd3; max-width: 520px; white-space: pre-wrap; word-break: break-word; }}

    @media (max-width: 768px) {{
      body {{ padding: 12px; }}
      h1 {{ font-size: 1.45rem; }}
    }}
  </style>
</head>
<body>
  <main class='container'>
    <header class='header'>
      <h1>Space_OdT Export Report</h1>
      <p class='subtitle'>Execution snapshot for generated exports and API artifact retrieval status.</p>
    </header>

    <section class='summary'>
      <article class='metric'><div class='metric-label'>Modules tracked</div><div class='metric-value'>{len(module_counts)}</div></article>
      <article class='metric'><div class='metric-label'>Status rows</div><div class='metric-value'>{len(status_rows)}</div></article>
      <article class='metric'><div class='metric-label'>OK</div><div class='metric-value'>{ok_count}</div></article>
      <article class='metric'><div class='metric-label'>Not found</div><div class='metric-value'>{not_found_count}</div></article>
      <article class='metric'><div class='metric-label'>Errors</div><div class='metric-value'>{error_count}</div></article>
    </section>

    <section class='cards'>
      <article class='card'>
        <h2>Foundation</h2>
        <ul>{base_list}</ul>
      </article>
      <article class='card'>
        <h2>V1 retrieval artifacts</h2>
        <ul>{artifact_list}</ul>
      </article>
    </section>

    <section class='table-wrap'>
      <table>
        <thead>
          <tr><th>Module</th><th>Method</th><th>Result</th><th>Count</th><th>Error</th></tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
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
