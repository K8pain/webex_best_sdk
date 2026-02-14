from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.person_settings.forwarding import (
    CallForwardingAlways,
    CallForwardingPerson,
    PersonForwardingSetting,
)

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'workspaces_configurar_desvio_prefijo53'


def configurar_desvio_prefijo53_workspace(
    *,
    token: str,
    workspace_id: str,
    extension: str,
    destination: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """
    Configura desvío incondicional del workspace a plataforma legacy con prefijo 53.
    """
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    # 2) Snapshot previo: leemos estado actual para trazabilidad y rollback manual.
    before = model_to_dict(api.workspace_settings.forwarding.read(entity_id=workspace_id, org_id=org_id))

    target_destination = destination or f'53{extension}'
    forwarding = PersonForwardingSetting(
        call_forwarding=CallForwardingPerson(
            always=CallForwardingAlways(
                enabled=True,
                destination=target_destination,
                destination_voicemail_enabled=False,
                ring_reminder_enabled=False,
            ),
            busy=CallForwardingPerson.default().busy,
            no_answer=CallForwardingPerson.default().no_answer,
        ),
        business_continuity=PersonForwardingSetting.default().business_continuity,
    )

    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'entity_id': workspace_id,
        'org_id': org_id,
        'settings': model_to_dict(forwarding),
    }
    log('before_read', {'before': before})
    log('configure_request', request)

    # 4) Ejecución del cambio contra Webex Calling.
    api.workspace_settings.forwarding.configure(entity_id=workspace_id, forwarding=forwarding, org_id=org_id)
    after = model_to_dict(api.workspace_settings.forwarding.read(entity_id=workspace_id, org_id=org_id))

    # 5) Resultado normalizado para logs/pipelines aguas abajo.
    result = {'status': 'success', 'api_response': {'before': before, 'after': after, 'request': request}}
    log('configure_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar desvío prefijo 53 para workspace')
    parser.add_argument('--token', default=None)
    parser.add_argument('--workspace-id', required=True)
    parser.add_argument('--extension', required=True)
    parser.add_argument('--destination', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = configurar_desvio_prefijo53_workspace(
        token=get_token(args.token),
        workspace_id=args.workspace_id,
        extension=args.extension,
        destination=args.destination,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
