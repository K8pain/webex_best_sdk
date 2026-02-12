from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .engine import MissingV21InputsError, V21Runner


def launch_v21_ui(*, token: str, out_dir: Path, host: str = '127.0.0.1', port: int = 8765) -> None:
    runner = V21Runner(token=token, out_dir=out_dir)

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
            self._send({'error': 'not found'}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != '/api/run-action':
                self._send({'error': 'not found'}, status=404)
                return
            query = parse_qs(parsed.query)
            try:
                action_id = int((query.get('action_id') or [''])[0])
                apply = (query.get('apply') or ['0'])[0] == '1'
                result = runner.run_single_action(action_id, apply=apply)
                self._send(result)
            except MissingV21InputsError as exc:
                self._send({'error': str(exc)}, status=400)
            except Exception as exc:  # pragma: no cover - defensive
                self._send({'error': str(exc)}, status=400)

        def log_message(self, format, *args):  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f'V2.1 UI listening on http://{host}:{port}')
    print('Use /api/plan and /api/run-action?action_id=<id>&apply=0|1')
    server.serve_forever()


def _html_page() -> str:
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <title>Space_OdT v2.1 Manual Closure UI</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 10px; }
    .meta { color: #444; font-size: 13px; }
    button { margin-right: 8px; }
    pre { background: #f6f6f6; padding: 8px; border-radius: 6px; overflow-x: auto; }
  </style>
</head>
<body>
  <h1>Space_OdT v2.1 - Acciones unitarias</h1>
  <p>Cada acción puede ejecutarse en <b>Preview</b> (before/after simulado) o <b>Apply</b>.</p>
  <div id="list"></div>
  <h2>Resultado before/after</h2>
  <pre id="result">(sin ejecución)</pre>

  <script>
    async function loadPlan() {
      const r = await fetch('/api/plan');
      const data = await r.json();
      const list = document.getElementById('list');
      if (data.error) {
        list.innerHTML = '<p style="color:red">' + data.error + '</p>';
        return;
      }
      list.innerHTML = '';
      for (const item of data.items) {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
          <div><b>#${item.action_id}</b> ${item.stage}</div>
          <div class="meta">${item.entity_type} :: ${item.entity_key}</div>
          <div>${item.details}</div>
          <div style="margin-top:8px;">
            <button onclick="runAction(${item.action_id}, false)">Preview</button>
            <button onclick="runAction(${item.action_id}, true)">Apply</button>
          </div>
        `;
        list.appendChild(card);
      }
    }

    async function runAction(actionId, apply) {
      const r = await fetch(`/api/run-action?action_id=${actionId}&apply=${apply ? 1 : 0}`, { method: 'POST' });
      const data = await r.json();
      document.getElementById('result').textContent = JSON.stringify(data, null, 2);
    }

    loadPlan();
  </script>
</body>
</html>
"""
