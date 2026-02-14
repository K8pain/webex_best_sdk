from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
import csv
import json
import logging
import traceback
from pathlib import Path
from typing import Any, Callable

from .common import get_token, load_runtime_env
from .ubicacion_actualizar_cabecera import actualizar_cabecera_ubicacion
from .ubicacion_alta_numeraciones_desactivadas import alta_numeraciones_desactivadas
from .ubicacion_configurar_llamadas_internas import configurar_llamadas_internas_ubicacion
from .ubicacion_configurar_permisos_salientes_defecto import configurar_permisos_salientes_defecto_ubicacion
from .ubicacion_configurar_pstn import configurar_pstn_ubicacion
from .usuarios_alta_people import alta_usuario_people
from .usuarios_alta_scim import alta_usuario_scim
from .usuarios_anadir_intercom_legacy import anadir_intercom_legacy_usuario
from .usuarios_configurar_desvio_prefijo53 import configurar_desvio_prefijo53_usuario
from .usuarios_configurar_perfil_saliente_custom import configurar_perfil_saliente_custom_usuario
from .usuarios_modificar_licencias import modificar_licencias_usuario
from .workspaces_alta import alta_workspace
from .workspaces_anadir_intercom_legacy import anadir_intercom_legacy_workspace
from .workspaces_configurar_desvio_prefijo53 import configurar_desvio_prefijo53_workspace
from .workspaces_configurar_perfil_saliente_custom import configurar_perfil_saliente_custom_workspace

ActionFn = Callable[..., dict[str, Any]]
DEFAULT_CSV = Path('.artifacts/exports/v21_transformacion_candidatos.csv')

HANDLERS: dict[str, ActionFn] = {
    'ubicacion_actualizar_cabecera': actualizar_cabecera_ubicacion,
    'ubicacion_alta_numeraciones_desactivadas': alta_numeraciones_desactivadas,
    'ubicacion_configurar_llamadas_internas': configurar_llamadas_internas_ubicacion,
    'ubicacion_configurar_permisos_salientes_defecto': configurar_permisos_salientes_defecto_ubicacion,
    'ubicacion_configurar_pstn': configurar_pstn_ubicacion,
    'usuarios_alta_people': alta_usuario_people,
    'usuarios_alta_scim': alta_usuario_scim,
    'usuarios_anadir_intercom_legacy': anadir_intercom_legacy_usuario,
    'usuarios_configurar_desvio_prefijo53': configurar_desvio_prefijo53_usuario,
    'usuarios_configurar_perfil_saliente_custom': configurar_perfil_saliente_custom_usuario,
    'usuarios_modificar_licencias': modificar_licencias_usuario,
    'workspaces_alta': alta_workspace,
    'workspaces_anadir_intercom_legacy': anadir_intercom_legacy_workspace,
    'workspaces_configurar_desvio_prefijo53': configurar_desvio_prefijo53_workspace,
    'workspaces_configurar_perfil_saliente_custom': configurar_perfil_saliente_custom_workspace,
}


LOGGER = logging.getLogger(__name__)


def _setup_debug_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    logging.getLogger('wxc_sdk').setLevel(logging.DEBUG)


def _read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open('r', encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def _confirm(script_name: str, auto_confirm: bool) -> bool:
    if auto_confirm:
        return True
    answer = input(f'¿Ejecutar {script_name}? [y/N]: ').strip().lower()
    return answer in {'y', 'yes', 's', 'si'}


def _run_row(*, row: dict[str, str], token: str, auto_confirm: bool, dry_run: bool) -> dict[str, Any]:
    script_name = row['script_name']
    if script_name not in HANDLERS:
        return {'script_name': script_name, 'status': 'rejected', 'reason': 'unsupported_script'}

    if row['candidate_status'] != 'ready':
        return {
            'script_name': script_name,
            'status': 'skipped',
            'reason': 'missing_dependencies',
            'missing_dependencies': row.get('missing_dependencies', ''),
        }

    params = json.loads(row['params_json'])
    invocation_payload = {
        'script_name': script_name,
        'method': HANDLERS[script_name].__name__,
        'kwargs': {'token': '***' if token else '', **params},
    }
    LOGGER.info('Invocación preparada:\n%s', json.dumps(invocation_payload, indent=2, ensure_ascii=False, sort_keys=True))

    if not _confirm(script_name, auto_confirm=auto_confirm):
        return {'script_name': script_name, 'status': 'skipped', 'reason': 'user_cancelled'}

    if dry_run:
        return {'script_name': script_name, 'status': 'dry_run', 'params': params, 'invocation': invocation_payload}

    try:
        # 5) Resultado normalizado para logs/pipelines aguas abajo.
        result = HANDLERS[script_name](token=token, **params)
    except Exception as exc:  # noqa: BLE001 - El launcher debe continuar con la siguiente fila.
        LOGGER.exception('Fallo ejecutando %s con params=%s', script_name, json.dumps(params, ensure_ascii=False, sort_keys=True))
        return {
            'script_name': script_name,
            'status': 'error',
            'error_type': type(exc).__name__,
            'error': str(exc),
            'params': params,
            'invocation': invocation_payload,
            'traceback': traceback.format_exc(),
        }

    return {'script_name': script_name, 'status': 'executed', 'result': result, 'invocation': invocation_payload}


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Launcher v21 que usa CSV de dependencias y confirma antes de ejecutar')
    parser.add_argument('--csv-path', type=Path, default=DEFAULT_CSV)
    parser.add_argument('--token', default=None)
    parser.add_argument('--script-name', action='append', default=None, help='Filtra por script_name (repetible)')
    parser.add_argument('--auto-confirm', action='store_true', help='Evita input() y confirma todo automáticamente')
    parser.add_argument('--dry-run', action='store_true', help='No llama API, solo valida y muestra payload a ejecutar')
    args = parser.parse_args()

    _setup_debug_logging()

    rows = _read_rows(args.csv_path)
    if args.script_name:
        wanted = set(args.script_name)
        rows = [row for row in rows if row['script_name'] in wanted]

    token = '' if args.dry_run else get_token(args.token)
    report: list[dict[str, Any]] = []
    for row in rows:
        report.append(_run_row(row=row, token=token, auto_confirm=args.auto_confirm, dry_run=args.dry_run))

    print(json.dumps({'csv_path': str(args.csv_path), 'results': report}, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
