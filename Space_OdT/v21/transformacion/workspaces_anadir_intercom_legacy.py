from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.workspace_settings.numbers import UpdateWorkspacePhoneNumber

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'workspaces_anadir_intercom_legacy'


def anadir_intercom_legacy_workspace(
    *,
    token: str,
    workspace_id: str,
    legacy_phone_number: str,
    org_id: str | None = None,
) -> dict[str, Any]:
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    # 2) Snapshot previo: leemos estado actual para trazabilidad y rollback manual.
    before = api.workspace_settings.numbers.read(workspace_id=workspace_id, org_id=org_id)
    before_payload = model_to_dict(before)
    already_exists = any((num.get('directNumber') == legacy_phone_number) for num in before_payload.get('phoneNumbers', []))
    if already_exists:
        # 5) Resultado normalizado para logs/pipelines aguas abajo.
        result = {
            'status': 'skipped',
            'reason': 'legacy_number_already_present',
            'api_response': {'before': before_payload},
        }
        log('update_skipped', {'workspace_id': workspace_id, 'legacy_phone_number': legacy_phone_number})
        return result

    update_numbers = [UpdateWorkspacePhoneNumber(action='ADD', direct_number=legacy_phone_number, primary=False)]
    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'workspace_id': workspace_id,
        'org_id': org_id,
        'phone_numbers': [model_to_dict(item) for item in update_numbers],
        'distinctive_ring_enabled': bool(before_payload.get('distinctiveRingEnabled', False)),
    }
    log('update_request', request)

    # 4) Ejecución del cambio contra Webex Calling.
    api.workspace_settings.numbers.update(
        workspace_id=workspace_id,
        phone_numbers=update_numbers,
        distinctive_ring_enabled=request['distinctive_ring_enabled'],
        org_id=org_id,
    )
    after = api.workspace_settings.numbers.read(workspace_id=workspace_id, org_id=org_id)
    after_payload = model_to_dict(after)

    result = {
        'status': 'success',
        'api_response': {'request': request, 'before': before_payload, 'after': after_payload},
    }
    log('update_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Añadir intercom legacy (número secundario) a workspace')
    parser.add_argument('--token', default=None)
    parser.add_argument('--workspace-id', required=True)
    parser.add_argument('--legacy-phone-number', required=True)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = anadir_intercom_legacy_workspace(
        token=get_token(args.token),
        workspace_id=args.workspace_id,
        legacy_phone_number=args.legacy_phone_number,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
