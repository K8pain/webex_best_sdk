from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
import json
from typing import Any, Callable
from urllib.request import Request, urlopen

from .common import get_token, load_runtime_env
from .ubicacion_actualizar_cabecera import actualizar_cabecera_ubicacion
from .ubicacion_alta_numeraciones_desactivadas import alta_numeraciones_desactivadas
from .ubicacion_configurar_pstn import configurar_pstn_ubicacion
from .ubicacion_configurar_llamadas_internas import configurar_llamadas_internas_ubicacion
from .ubicacion_configurar_permisos_salientes_defecto import configurar_permisos_salientes_defecto_ubicacion
from .usuarios_alta_people import alta_usuario_people
from .usuarios_alta_scim import alta_usuario_scim
from .usuarios_anadir_intercom_legacy import anadir_intercom_legacy_usuario
from .usuarios_modificar_licencias import modificar_licencias_usuario
from .usuarios_configurar_desvio_prefijo53 import configurar_desvio_prefijo53_usuario
from .usuarios_configurar_perfil_saliente_custom import configurar_perfil_saliente_custom_usuario
from .workspaces_alta import alta_workspace
from .workspaces_anadir_intercom_legacy import anadir_intercom_legacy_workspace
from .workspaces_configurar_desvio_prefijo53 import configurar_desvio_prefijo53_workspace
from .workspaces_configurar_perfil_saliente_custom import configurar_perfil_saliente_custom_workspace

ActionFn = Callable[..., dict[str, Any]]


def _load_remote_payload(remote_url: str, timeout_s: float) -> dict[str, Any]:
    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = Request(remote_url, headers={'Accept': 'application/json'})
    with urlopen(request, timeout=timeout_s) as response:
        raw = response.read().decode('utf-8')
    return json.loads(raw)


def _execute_actions(*, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    handlers: dict[str, ActionFn] = {
        'ubicacion_configurar_pstn': configurar_pstn_ubicacion,
        'ubicacion_alta_numeraciones_desactivadas': alta_numeraciones_desactivadas,
        'ubicacion_actualizar_cabecera': actualizar_cabecera_ubicacion,
        'ubicacion_configurar_llamadas_internas': configurar_llamadas_internas_ubicacion,
        'ubicacion_configurar_permisos_salientes_defecto': configurar_permisos_salientes_defecto_ubicacion,
        'usuarios_alta_people': alta_usuario_people,
        'usuarios_alta_scim': alta_usuario_scim,
        'usuarios_modificar_licencias': modificar_licencias_usuario,
        'usuarios_anadir_intercom_legacy': anadir_intercom_legacy_usuario,
        'usuarios_configurar_desvio_prefijo53': configurar_desvio_prefijo53_usuario,
        'usuarios_configurar_perfil_saliente_custom': configurar_perfil_saliente_custom_usuario,
        'workspaces_alta': alta_workspace,
        'workspaces_anadir_intercom_legacy': anadir_intercom_legacy_workspace,
        'workspaces_configurar_desvio_prefijo53': configurar_desvio_prefijo53_workspace,
        'workspaces_configurar_perfil_saliente_custom': configurar_perfil_saliente_custom_workspace,
    }

    report: dict[str, Any] = {'source': payload.get('meta', {}), 'results': []}
    for action in payload.get('acciones', []):
        action_name = action['action']
        params = dict(action.get('params', {}))
        if action_name not in handlers:
            report['results'].append({'action': action_name, 'status': 'rejected', 'reason': 'unsupported_action'})
            continue
        # 5) Resultado normalizado para logs/pipelines aguas abajo.
        result = handlers[action_name](token=token, **params)
        report['results'].append({'action': action_name, 'result': result})
    return report


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Launcher tester para consumir acciones desde API remota')
    parser.add_argument('--token', default=None)
    parser.add_argument('--remote-url', required=True, help='Endpoint que devuelve JSON con acciones a ejecutar')
    parser.add_argument('--timeout-s', type=float, default=10.0)
    args = parser.parse_args()

    token = get_token(args.token)
    payload = _load_remote_payload(args.remote_url, timeout_s=args.timeout_s)
    report = _execute_actions(token=token, payload=payload)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
