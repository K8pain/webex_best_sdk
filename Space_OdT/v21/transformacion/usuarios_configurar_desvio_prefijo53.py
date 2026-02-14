from __future__ import annotations

import argparse
from typing import Any

from wxc_sdk.person_settings.forwarding import (
    CallForwardingAlways,
    CallForwardingPerson,
    PersonForwardingSetting,
)

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'usuarios_configurar_desvio_prefijo53'


def configurar_desvio_prefijo53_usuario(
    *,
    token: str,
    person_id: str,
    extension: str,
    destination: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """
    Configura desvío incondicional del usuario a plataforma legacy con prefijo 53.
    """
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    before = model_to_dict(api.person_settings.forwarding.read(entity_id=person_id, org_id=org_id))

    target_destination = destination or f'53{extension}'
    forwarding = PersonForwardingSetting(
        call_forwarding=CallForwardingPerson(
            always=CallForwardingAlways(
                enabled=True,
                destination=target_destination,
                destination_voicemail_enabled=False,
                ring_reminder_enabled=False,
            )
        )
    )
    request = {
        'entity_id': person_id,
        'org_id': org_id,
        'forwarding': model_to_dict(forwarding),
    }

    log('before_read', {'before': before})
    log('configure_request', request)

    api.person_settings.forwarding.configure(entity_id=person_id, forwarding=forwarding, org_id=org_id)
    after = model_to_dict(api.person_settings.forwarding.read(entity_id=person_id, org_id=org_id))

    result = {'status': 'success', 'api_response': {'before': before, 'after': after, 'request': request}}
    log('configure_response', result)
    return result


def main() -> None:
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar desvío incondicional a prefijo 53 para un usuario')
    parser.add_argument('--token', default=None)
    parser.add_argument('--person-id', required=True)
    parser.add_argument('--extension', required=True, help='Extensión base para construir destino 53+extension')
    parser.add_argument('--destination', default=None, help='Destino explícito, si no se usa 53+extension')
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = configurar_desvio_prefijo53_usuario(
        token=get_token(args.token),
        person_id=args.person_id,
        extension=args.extension,
        destination=args.destination,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
