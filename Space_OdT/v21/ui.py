from __future__ import annotations

import csv
import datetime as dt
import io
import json
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .engine import MissingV21InputsError, V21Runner
from .io import load_locations_from_json
from .transformacion.ubicacion_actualizar_cabecera import actualizar_cabecera_ubicacion
from .transformacion.ubicacion_alta_numeraciones_desactivadas import alta_numeraciones_desactivadas
from .transformacion.ubicacion_configurar_pstn import configurar_pstn_ubicacion
from wxc_sdk.telephony.location.numbers import TelephoneNumberType


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
            if parsed.path == '/api/location-ids':
                org_id = (parse_qs(parsed.query).get('orgId') or [''])[0]
                if not org_id:
                    self._send({'error': 'orgId es obligatorio'}, status=400)
                    return
                try:
                    payload = _run_async(runner.list_location_ids(org_id=org_id))
                    self._send(payload)
                except Exception as exc:  # noqa: BLE001
                    self._send({'error': str(exc)}, status=400)
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
            if parsed.path == '/api/transformacion/configurar-pstn':
                try:
                    payload = self._parse_json_body()
                    result = configurar_pstn_ubicacion(
                        token=runner.token,
                        location_id=str(payload.get('locationId') or '').strip(),
                        premise_route_type=str(payload.get('premiseRouteType') or 'ROUTE_GROUP').strip(),
                        premise_route_id=str(payload.get('premiseRouteId') or '').strip(),
                        org_id=str(payload.get('orgId') or '').strip() or None,
                    )
                    self._send(result)
                except Exception as exc:  # noqa: BLE001
                    self._send({'status': 'error', 'error': str(exc)}, status=400)
                return

            if parsed.path == '/api/transformacion/alta-numeraciones':
                try:
                    payload = self._parse_json_body()
                    phone_numbers = payload.get('phoneNumbers') or []
                    if isinstance(phone_numbers, str):
                        phone_numbers = [line.strip() for line in phone_numbers.splitlines() if line.strip()]
                    result = alta_numeraciones_desactivadas(
                        token=runner.token,
                        location_id=str(payload.get('locationId') or '').strip(),
                        phone_numbers=phone_numbers,
                        number_type=TelephoneNumberType(str(payload.get('numberType') or 'DID').strip()),
                        org_id=str(payload.get('orgId') or '').strip() or None,
                    )
                    self._send(result)
                except Exception as exc:  # noqa: BLE001
                    self._send({'status': 'error', 'error': str(exc)}, status=400)
                return

            if parsed.path == '/api/transformacion/actualizar-cabecera':
                try:
                    payload = self._parse_json_body()
                    result = actualizar_cabecera_ubicacion(
                        token=runner.token,
                        location_id=str(payload.get('locationId') or '').strip(),
                        phone_number=str(payload.get('phoneNumber') or '').strip(),
                        calling_line_name=str(payload.get('callingLineName') or '').strip() or None,
                        org_id=str(payload.get('orgId') or '').strip() or None,
                    )
                    self._send(result)
                except Exception as exc:  # noqa: BLE001
                    self._send({'status': 'error', 'error': str(exc)}, status=400)
                return

            if parsed.path in {'/api/location-jobs', '/api/location-wbxc-jobs'}:
                try:
                    rows, preview = self._parse_upload()
                    entity_type = 'location' if parsed.path == '/api/location-jobs' else 'location_webex_calling'
                    job = runner.create_location_job(rows=rows, entity_type=entity_type)
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

        def _parse_json_body(self) -> dict:
            content_length = int(self.headers.get('Content-Length', '0'))
            raw = self.rfile.read(content_length)
            ctype = self.headers.get('Content-Type', '')
            if 'application/json' not in ctype:
                raise ValueError('Content-Type debe ser application/json')
            payload = json.loads(raw.decode('utf-8'))
            if not isinstance(payload, dict):
                raise ValueError('El payload JSON debe ser un objeto')
            return payload

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
    except Exception as exc:  # noqa: BLE001
        failure = {
            'failed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'error_type': type(exc).__name__,
            'error_message': str(exc),
            'traceback': traceback.format_exc(),
        }
        job = runner.get_job(job_id)
        job.status = 'failed'
        job.last_error = failure
        runner.save_job(job)
        failure_path = runner.jobs_dir / job_id / 'failure.json'
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        failure_path.write_text(json.dumps(failure, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def _run_async(awaitable):
    import asyncio

    return asyncio.run(awaitable)


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
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>Space_OdT v2.1 · Transformación Ubicación</title>
  <style>
    :root {
      --bg: #083f1f;
      --panel: #0f6b31;
      --panel-2: #0d5b2a;
      --line: #2ea15a;
      --text: #f3fff6;
      --muted: #c9f5d8;
      --accent: #ffde59;
      --danger: #ffd2d2;
      --sidebar: #052d15;
      --sidebar-active: #1a8e43;
    }
    * { box-sizing: border-box; }
    body { font-family: Inter, Arial, sans-serif; margin: 0; background: var(--bg); color: var(--text); }
    .layout { display: grid; grid-template-columns: 310px 1fr; min-height: 100vh; }
    .sidebar { background: var(--sidebar); border-right: 1px solid #176a35; padding: 16px 12px; }
    .brand { color: var(--accent); margin: 0 0 14px; font-size: 18px; }
    .menu button { display:block; width:100%; text-align:left; margin:0 0 8px; border:1px solid #176a35; background:#0a4a24; color:var(--text); border-radius:8px; padding:10px; cursor:pointer; font-weight:600; }
    .menu button.active { background: var(--sidebar-active); }
    .menu small { display:block; color: var(--muted); font-weight:500; margin-top:4px; }
    .content { padding: 20px; }
    .card { background: linear-gradient(180deg, var(--panel) 0%, var(--panel-2) 100%); border: 1px solid var(--line); border-radius: 10px; padding: 14px; margin-bottom: 14px; }
    h1 { margin-top: 0; color: var(--accent); }
    p.lead { color: var(--muted); margin-top: -6px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
    button { border: 1px solid #1d8e45; background: #18863f; color: #fff; border-radius: 8px; padding: 9px 12px; cursor: pointer; font-weight: 600; }
    input, textarea, select { width:100%; padding:8px; border-radius:8px; border:1px solid #1d8e45; background:#0a4a24; color:#fff; margin-bottom:8px; }
    textarea { min-height: 90px; }
    pre { background: #072f17; color: #d9ffe6; padding: 10px; border-radius: 8px; overflow-x: auto; max-height: 420px; border: 1px solid #1e8842; }
    .error { color: var(--danger); }
    .muted { color: var(--muted); }
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <h2 class="brand">Space_OdT v2.1</h2>
      <nav class="menu">
        <button id="menu-configurar_pstn" class="active" onclick="selectAction('configurar_pstn')">Configurar PSTN de ubicación<small>premiseRouteType + premiseRouteId</small></button>
        <button id="menu-alta_numeraciones" onclick="selectAction('alta_numeraciones')">Alta numeraciones en ubicación<small>state INACTIVE</small></button>
        <button id="menu-anadir_cabecera" onclick="selectAction('anadir_cabecera')">Añadir cabecera de Ubicación<small>calling_line_id.phone_number</small></button>
      </nav>
    </aside>
    <main class="content">
      <h1 id="screenTitle">Space_OdT v2.1 · Configurar PSTN de ubicación</h1>
      <p class="lead" id="screenLead">UI operativa para técnicos de telefonía, ejecutando scripts SDK reales y mostrando respuesta API real.</p>

      <div class="card">
        <h3>Definición funcional</h3>
        <p id="actionDescription" class="muted"></p>
        <p><b>Nota importante:</b> <span id="importantNote"></span></p>
        <p><b>Campos obligatorios:</b></p>
        <ul id="mandatoryFields"></ul>
      </div>

      <div class="card" id="formCard">
        <h3>Ejecutar cambio</h3>
        <div id="formArea"></div>
        <div class="actions">
          <button onclick="executeAction()">Ejecutar acción</button>
        </div>
      </div>

      <div class="card">
        <h3>Respuesta API (real)</h3>
        <div id="errorSummary"></div>
        <pre id="finalConfig">Aquí se verá la respuesta API real devuelta por backend/script SDK.</pre>
      </div>
    </main>
  </div>

  <script>
    let currentAction = 'configurar_pstn';

    const ACTIONS = {
      configurar_pstn: {
        title: 'Space_OdT v2.1 · Configurar PSTN de ubicación',
        lead: 'Conecta la ubicación a PSTN tipo ROUTE_GROUP o TRUNK.',
        description: 'Ejecuta script SDK real: lee estado actual PSTN, aplica configuración y devuelve before/after reales.',
        mandatoryFields: ['locationId', 'premiseRouteType', 'premiseRouteId'],
        note: 'Para el caso operativo habitual usar premiseRouteType=ROUTE_GROUP.',
        endpoint: '/api/transformacion/configurar-pstn',
        fields: [
          { key: 'locationId', label: 'Location ID', type: 'text', placeholder: 'Y2lzY29zcGFyazovL3VzL0xPQ0FUSU9OLy4uLg==' },
          { key: 'orgId', label: 'Org ID (opcional)', type: 'text', placeholder: 'Y2lzY29zcGFyazovL3VzL09SR0FOSVpBVElPTi8uLi4=' },
          { key: 'premiseRouteType', label: 'Premise Route Type', type: 'select', options: ['ROUTE_GROUP', 'TRUNK'] },
          { key: 'premiseRouteId', label: 'Premise Route ID', type: 'text', placeholder: 'route-group-or-trunk-id' },
        ],
      },
      alta_numeraciones: {
        title: 'Space_OdT v2.1 · Alta numeraciones en ubicación',
        lead: 'Carga numeraciones DID/TOLLFREE/MOBILE en estado INACTIVE.',
        description: 'Ejecuta script SDK real: lista números de la ubicación, añade bloque y devuelve respuesta real de alta.',
        mandatoryFields: ['locationId', 'phoneNumbers[]', 'numberType'],
        note: 'Ingresar una numeración por línea en formato E.164 (+34...).',
        endpoint: '/api/transformacion/alta-numeraciones',
        fields: [
          { key: 'locationId', label: 'Location ID', type: 'text', placeholder: 'Y2lzY29zcGFyazovL3VzL0xPQ0FUSU9OLy4uLg==' },
          { key: 'orgId', label: 'Org ID (opcional)', type: 'text', placeholder: 'Y2lzY29zcGFyazovL3VzL09SR0FOSVpBVElPTi8uLi4=' },
          { key: 'numberType', label: 'Number Type', type: 'select', options: ['DID', 'TOLLFREE', 'MOBILE'] },
          { key: 'phoneNumbers', label: 'Phone Numbers (una por línea)', type: 'textarea', placeholder: '+34910000001\n+34910000002' },
        ],
      },
      anadir_cabecera: {
        title: 'Space_OdT v2.1 · Añadir cabecera de Ubicación',
        lead: 'Actualiza la cabecera de ubicación (calling line) con DDI de cabecera.',
        description: 'Ejecuta script SDK real: lee details de telephony location, aplica update y devuelve before/after reales.',
        mandatoryFields: ['locationId', 'phoneNumber'],
        note: 'Opcionalmente puede enviarse callingLineName para actualizar el nombre de cabecera.',
        endpoint: '/api/transformacion/actualizar-cabecera',
        fields: [
          { key: 'locationId', label: 'Location ID', type: 'text', placeholder: 'Y2lzY29zcGFyazovL3VzL0xPQ0FUSU9OLy4uLg==' },
          { key: 'orgId', label: 'Org ID (opcional)', type: 'text', placeholder: 'Y2lzY29zcGFyazovL3VzL09SR0FOSVpBVElPTi8uLi4=' },
          { key: 'phoneNumber', label: 'Cabecera phone number', type: 'text', placeholder: '+34910000001' },
          { key: 'callingLineName', label: 'Cabecera name (opcional)', type: 'text', placeholder: 'SEDE MADRID' },
        ],
      },
    };

    window.addEventListener('DOMContentLoaded', () => {
      applyActionMeta();
    });

    function selectAction(action) {
      currentAction = action;
      Object.keys(ACTIONS).forEach((key) => {
        document.getElementById(`menu-${key}`).classList.toggle('active', key === action);
      });
      applyActionMeta();
    }

    function applyActionMeta() {
      const meta = ACTIONS[currentAction];
      document.getElementById('screenTitle').textContent = meta.title;
      document.getElementById('screenLead').textContent = meta.lead;
      document.getElementById('actionDescription').textContent = meta.description;
      document.getElementById('importantNote').textContent = meta.note;
      document.getElementById('mandatoryFields').innerHTML = meta.mandatoryFields.map(f => `<li>${f}</li>`).join('');
      renderForm(meta.fields);
      document.getElementById('finalConfig').textContent = 'Aquí se verá la respuesta API real devuelta por backend/script SDK.';
      document.getElementById('errorSummary').innerHTML = '';
    }

    function renderForm(fields) {
      const area = document.getElementById('formArea');
      area.innerHTML = fields.map((field) => {
        if (field.type === 'select') {
          return `<label><b>${field.label}</b><select id="field-${field.key}">${field.options.map(opt => `<option value="${opt}">${opt}</option>`).join('')}</select></label>`;
        }
        if (field.type === 'textarea') {
          return `<label><b>${field.label}</b><textarea id="field-${field.key}" placeholder="${field.placeholder || ''}"></textarea></label>`;
        }
        return `<label><b>${field.label}</b><input id="field-${field.key}" type="text" placeholder="${field.placeholder || ''}" /></label>`;
      }).join('');
    }

    function collectPayload() {
      const meta = ACTIONS[currentAction];
      const payload = {};
      meta.fields.forEach((field) => {
        const el = document.getElementById(`field-${field.key}`);
        if (!el) return;
        const value = (el.value || '').trim();
        if (field.key === 'phoneNumbers') {
          payload.phoneNumbers = value;
          return;
        }
        payload[field.key] = value;
      });
      return payload;
    }

    async function executeAction() {
      const meta = ACTIONS[currentAction];
      const payload = collectPayload();
      const r = await fetch(meta.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      if (!r.ok || data.error) {
        document.getElementById('errorSummary').innerHTML = `<span class="error">Error: ${data.error || 'Error de ejecución'}</span>`;
      } else {
        document.getElementById('errorSummary').innerHTML = '<span class="muted">Acción ejecutada correctamente contra API.</span>';
      }
      document.getElementById('finalConfig').textContent = JSON.stringify(data, null, 2);
    }
  </script>
</body>
</html>
"""
