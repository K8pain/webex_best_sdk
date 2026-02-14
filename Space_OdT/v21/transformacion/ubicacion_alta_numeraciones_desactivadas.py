from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.common import NumberState
from wxc_sdk.telephony.location.numbers import TelephoneNumberType

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'ubicacion_alta_numeraciones_desactivadas'


def alta_numeraciones_desactivadas(
    *,
    token: str,
    location_id: str,
    phone_numbers: list[str],
    number_type: TelephoneNumberType = TelephoneNumberType.did,
    org_id: str | None = None,
) -> dict[str, Any]:
    if not phone_numbers:
        raise ValueError('phone_numbers no puede ser vacío')

    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)
    # 2) Snapshot previo: leemos estado actual para trazabilidad y rollback manual.
    before = [model_to_dict(item) for item in api.telephony.location.phone_numbers(location_id=location_id, org_id=org_id)]
    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'location_id': location_id,
        'phone_numbers': phone_numbers,
        'number_type': str(number_type),
        'state': NumberState.inactive.value,
        'org_id': org_id,
    }
    log('before_read', {'before': before})
    log('add_numbers_request', request)

    add_response = api.telephony.location.number.add(
        location_id=location_id,
        phone_numbers=phone_numbers,
        number_type=number_type,
        state=NumberState.inactive,
        org_id=org_id,
    )

    after = [model_to_dict(item) for item in api.telephony.location.phone_numbers(location_id=location_id, org_id=org_id)]
    # 5) Resultado normalizado para logs/pipelines aguas abajo.
    result = {
        'status': 'success',
        'api_response': {
            'before': before,
            'after': after,
            'request': request,
            'add_response': model_to_dict(add_response),
        },
    }
    log('add_numbers_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Alta numeraciones en ubicación (estado desactivado)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--location-id', required=True)
    parser.add_argument('--phone-number', action='append', required=True, dest='phone_numbers')
    parser.add_argument('--number-type', default='DID', choices=['DID', 'TOLLFREE', 'MOBILE'])
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = alta_numeraciones_desactivadas(
        token=get_token(args.token),
        location_id=args.location_id,
        phone_numbers=args.phone_numbers,
        number_type=TelephoneNumberType(args.number_type),
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
