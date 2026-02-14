from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.workspaces import Workspace

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'workspaces_alta'


def alta_workspace(
    *,
    token: str,
    display_name: str,
    location_id: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """
    Alta de workspace con validación previa básica por nombre/location.
    """
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    existing = list(api.workspaces.list(display_name=display_name, location_id=location_id, org_id=org_id))
    existing_payload = model_to_dict(existing)
    if existing_payload:
        # 5) Resultado normalizado para logs/pipelines aguas abajo.
        result = {
            'status': 'skipped',
            'reason': 'workspace_already_exists',
            'api_response': {'existing': existing_payload},
        }
        log('create_skipped', {'display_name': display_name, 'location_id': location_id, 'org_id': org_id})
        return result

    workspace = Workspace.create(display_name=display_name)
    if location_id:
        workspace.location_id = location_id

    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {'workspace': model_to_dict(workspace), 'org_id': org_id}
    log('create_request', request)

    created = api.workspaces.create(settings=workspace, org_id=org_id)
    created_payload = model_to_dict(created)

    result = {'status': 'success', 'api_response': {'request': request, 'created': created_payload}}
    log('create_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Alta de workspace en Webex Calling')
    parser.add_argument('--token', default=None)
    parser.add_argument('--display-name', required=True)
    parser.add_argument('--location-id', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = alta_workspace(
        token=get_token(args.token),
        display_name=args.display_name,
        location_id=args.location_id,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
