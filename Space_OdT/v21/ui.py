from __future__ import annotations

import csv
import io
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .engine import MissingV21InputsError, V21Runner
from .io import LOCATION_HEADERS, LOCATION_REQUIRED_CREATE_FIELDS, load_locations_from_json


def launch_v21_ui(*, token: str, out_dir: Path, host: str = '127.0.0.1', port: int = 8765) -> None:
    runner = V21Runner(token=token, out_dir=out_dir)
    running_jobs: dict[str, threading.Thread] = {}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload: dict, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == '/':
                html = _html_page().encode('utf-8')
                self.send_response(HTTPStatus.OK)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if parsed.path == '/api/plan':
                try:
                    self._send({'items': runner.load_plan_rows()})
                except MissingV21InputsError as exc:
                    self._send({'error': str(exc)}, status=400)
                return
            if parsed.path == '/api/location-state/current':
                self._send(runner.get_latest_final_state())
                return
            if parsed.path == '/api/location-jobs/async-info':
                self._send(runner.get_async_execution_info())
                return
            if parsed.path.startswith('/api/location-jobs/'):
                path_parts = [part for part in parsed.path.split('/') if part]
                if len(path_parts) == 3:
                    _, _, job_id = path_parts
                    try:
                        self._send(runner.get_job(job_id).to_dict())
                    except FileNotFoundError:
                        self._send({'error': 'job not found'}, status=404)
                    return
                if len(path_parts) == 4 and path_parts[-1] == 'result':
                    job_id = path_parts[2]
                    try:
                        self._send(runner.get_job_result(job_id))
                    except FileNotFoundError as exc:
                        self._send({'error': str(exc)}, status=404)
                    return
            self._send({'error': 'not found'}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == '/api/location-jobs':
                try:
                    rows, preview = self._parse_upload()
                    job = runner.create_location_job(rows=rows, entity_type='location')
                    self._send({'job': job.to_dict(), 'count': len(rows), 'preview': preview})
                except Exception as exc:  # noqa: BLE001
                    self._send({'error': str(exc)}, status=400)
                return

            if parsed.path.startswith('/api/location-jobs/') and parsed.path.endswith('/start'):
                path_parts = [part for part in parsed.path.split('/') if part]
                if len(path_parts) != 4:
                    self._send({'error': 'invalid path'}, status=400)
                    return
                job_id = path_parts[2]
                try:
                    job = runner.get_job(job_id)
                except FileNotFoundError:
                    self._send({'error': 'job not found'}, status=404)
                    return

                if job.status == 'running':
                    self._send({'job': job.to_dict(), 'message': 'job already running'})
                    return

                thread = threading.Thread(target=_run_job_background, args=(runner, job_id), daemon=True)
                thread.start()
                running_jobs[job_id] = thread
                self._send({'job': job.to_dict(), 'message': 'job started'})
                return

            self._send({'error': 'not found'}, status=404)

        def _parse_upload(self) -> tuple[list[dict], list[dict]]:
            content_length = int(self.headers.get('Content-Length', '0'))
            raw = self.rfile.read(content_length)
            ctype = self.headers.get('Content-Type', '')

            if 'application/json' in ctype:
                payload = json.loads(raw.decode('utf-8'))
                if not isinstance(payload, list):
                    raise ValueError('JSON debe ser una lista de objetos')
                rows = payload
            elif 'multipart/form-data' in ctype:
                boundary = ctype.split('boundary=')[-1].encode('utf-8')
                rows = _rows_from_multipart(raw, boundary)
            else:
                raise ValueError('Content-Type no soportado, usar multipart/form-data o application/json')

            parsed_rows = load_locations_from_json(rows)
            normalized_rows = [row.payload for row in parsed_rows]
            return normalized_rows, normalized_rows[:10]

        def log_message(self, format, *args):  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f'V2.1 UI listening on http://{host}:{port}')
    server.serve_forever()


def _run_job_background(runner: V21Runner, job_id: str) -> None:
    import asyncio

    try:
        asyncio.run(runner.process_location_job(job_id, chunk_size=200, max_concurrency=20))
    except Exception:  # noqa: BLE001
        job = runner.get_job(job_id)
        job.status = 'failed'
        runner.save_job(job)


def _rows_from_multipart(raw: bytes, boundary: bytes) -> list[dict]:
    parts = raw.split(b'--' + boundary)
    file_name = ''
    file_bytes = b''
    for part in parts:
        if b'filename=' not in part:
            continue
        header, _, content = part.partition(b'\r\n\r\n')
        disposition = header.decode('utf-8', errors='ignore')
        marker = 'filename="'
        if marker in disposition:
            file_name = disposition.split(marker, 1)[1].split('"', 1)[0]
        file_bytes = content.rstrip(b'\r\n-')
        break
    if not file_name:
        raise ValueError('No se recibió archivo')

    ext = Path(file_name).suffix.lower()
    if ext == '.csv':
        text = file_bytes.decode('utf-8-sig')
        return list(csv.DictReader(io.StringIO(text)))
    if ext == '.json':
        payload = json.loads(file_bytes.decode('utf-8'))
        if not isinstance(payload, list):
            raise ValueError('JSON debe ser una lista de objetos')
        return payload
    raise ValueError('Solo se aceptan archivos .csv o .json')


def _html_page() -> str:
    required = ''.join(
        f"<li><code>{field}</code>{' <b>(obligatorio)</b>' if field in LOCATION_REQUIRED_CREATE_FIELDS else ''}</li>"
        for field in LOCATION_HEADERS
    )
    return f"""<!doctype html>
<html lang=\"es\">
<head>
  <meta charset=\"utf-8\" />
  <title>Space_OdT v2.1 location jobs</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; max-width: 1100px; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 14px; }}
    .progress {{ width: 100%; height: 18px; background: #eee; border-radius: 12px; overflow: hidden; }}
    .progress > div {{ height: 100%; background: #3d7eff; width: 0%; }}
    button {{ margin-right: 8px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 6px; font-size: 12px; }}
    pre {{ background: #f6f6f6; padding: 8px; border-radius: 6px; overflow-x: auto; max-height: 250px; }}
  </style>
</head>
<body>
  <h1>Space_OdT v2.1 - Location Bulk Jobs</h1>

  <div class=\"card\">
    <h3>Estado actual (antes de cargar)</h3>
    <button onclick=\"loadCurrentState()\">Ver estado actual</button>
    <div id=\"currentStateInfo\"></div>
    <div id=\"currentStateTable\"></div>
  </div>

  <div class=\"card\">
    <h3>Upload</h3>
    <input id=\"file\" type=\"file\" accept=\".csv,.json\" />
    <button onclick=\"createJob()\">Crear job</button>
    <div id=\"uploadInfo\"></div>
    <div id=\"preview\"></div>
  </div>

  <div class=\"card\">
    <h3>Campos obligatorios</h3>
    <ul>{required}</ul>
  </div>

  <div class=\"card\">
    <h3>Ejecución (acción unitaria)</h3>
    <button onclick=\"startJob()\">Apply</button>
    <button onclick=\"refreshJob()\">Actualizar estado</button>
    <div id=\"jobStatus\"></div>
    <div class=\"progress\"><div id=\"bar\"></div></div>
    <div id=\"errorSummary\"></div>
    <button onclick=\"showFinalConfig()\">Ver configuración final</button>
    <pre id=\"finalConfig\"></pre>
    <h4>Confirmación ejecución asíncrona</h4>
    <pre id=\"asyncInfo\"></pre>
  </div>

  <script>
    let currentJobId = null;

    window.addEventListener('DOMContentLoaded', () => {{
      loadCurrentState();
      loadAsyncInfo();
    }});

    async function loadCurrentState() {{
      const r = await fetch('/api/location-state/current');
      const data = await r.json();
      const source = data.source || 'none';
      const items = data.items || [];
      document.getElementById('currentStateInfo').innerHTML = `Fuente: <code>${{source}}</code> | Items: <b>${{items.length}}</b>`;
      renderTable('currentStateTable', items);
    }}

    async function loadAsyncInfo() {{
      const r = await fetch('/api/location-jobs/async-info');
      const data = await r.json();
      document.getElementById('asyncInfo').textContent = JSON.stringify(data, null, 2);
    }}

    async function createJob() {{
      const fileEl = document.getElementById('file');
      if (!fileEl.files.length) {{
        alert('Seleccioná un archivo CSV o JSON');
        return;
      }}
      const fd = new FormData();
      fd.append('file', fileEl.files[0]);
      const r = await fetch('/api/location-jobs', {{ method: 'POST', body: fd }});
      const data = await r.json();
      if (data.error) {{
        document.getElementById('uploadInfo').innerHTML = '<span style="color:red">' + data.error + '</span>';
        return;
      }}
      currentJobId = data.job.job_id;
      document.getElementById('uploadInfo').innerHTML = `Job <code>${{currentJobId}}</code> creado con ${{data.count}} filas`;
      renderTable('preview', data.preview || []);
      renderJob(data.job);
    }}

    async function startJob() {{
      if (!currentJobId) {{ alert('Primero creá un job'); return; }}
      const r = await fetch(`/api/location-jobs/${{currentJobId}}/start`, {{ method: 'POST' }});
      const data = await r.json();
      if (data.error) {{ alert(data.error); return; }}
      renderJob(data.job);
      pollUntilDone();
    }}

    async function refreshJob() {{
      if (!currentJobId) return;
      const r = await fetch(`/api/location-jobs/${{currentJobId}}`);
      const data = await r.json();
      if (!data.error) renderJob(data);
    }}

    async function pollUntilDone() {{
      for (let i = 0; i < 120; i++) {{
        await refreshJob();
        const status = document.getElementById('jobStatus').dataset.status;
        if (status === 'completed' || status === 'failed') return;
        await new Promise(res => setTimeout(res, 1200));
      }}
    }}

    async function showFinalConfig() {{
      if (!currentJobId) return;
      const r = await fetch(`/api/location-jobs/${{currentJobId}}/result`);
      const data = await r.json();
      if (data.error) {{
        document.getElementById('finalConfig').textContent = data.error;
        return;
      }}
      document.getElementById('finalConfig').textContent = JSON.stringify(data, null, 2);
      const errors = data.totals?.rejected || 0;
      document.getElementById('errorSummary').innerHTML = `Errores rechazados: <b>${{errors}}</b>`;
    }}

    function renderJob(job) {{
      const totals = job.totals || {{}};
      const processed = totals.processed || 0;
      const total = totals.total || 0;
      const pct = total ? Math.floor((processed / total) * 100) : 0;
      const label = `Estado: <b>${{job.status}}</b> | Procesadas: ${{processed}}/${{total}} | OK: ${{totals.success||0}} | Rechazadas: ${{totals.rejected||0}}`;
      const el = document.getElementById('jobStatus');
      el.innerHTML = label;
      el.dataset.status = job.status;
      document.getElementById('bar').style.width = pct + '%';
    }}

    function renderTable(targetId, items) {{
      const target = document.getElementById(targetId);
      if (!items.length) {{
        target.innerHTML = '<p>(sin datos)</p>';
        return;
      }}
      const headers = Object.keys(items[0]);
      const thead = '<tr>' + headers.map(h => `<th>${{h}}</th>`).join('') + '</tr>';
      const rows = items.map(row => '<tr>' + headers.map(h => `<td>${{row[h] ?? ''}}</td>`).join('') + '</tr>').join('');
      target.innerHTML = `<table><thead>${{thead}}</thead><tbody>${{rows}}</tbody></table>`;
    }}
  </script>
</body>
</html>
"""
