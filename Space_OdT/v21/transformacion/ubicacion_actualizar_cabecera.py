from __future__ import annotations

import argparse
from typing import Any

from wxc_sdk.telephony.location import CallingLineId

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'ubicacion_actualizar_cabecera'


def actualizar_cabecera_ubicacion(
    *,
    token: str,
    location_id: str,
    phone_number: str,
    org_id: str | None = None,
    calling_line_name: str | None = None,
) -> dict[str, Any]:
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)
    before = model_to_dict(api.telephony.location.details(location_id=location_id, org_id=org_id))

    settings = api.telephony.location.details(location_id=location_id, org_id=org_id)
    if settings.calling_line_id is None:
        settings.calling_line_id = CallingLineId(phone_number=phone_number)
    else:
        settings.calling_line_id.phone_number = phone_number
    if calling_line_name:
        if settings.calling_line_id is None:
            settings.calling_line_id = CallingLineId(name=calling_line_name, phone_number=phone_number)
        else:
            settings.calling_line_id.name = calling_line_name

    request = {
        'location_id': location_id,
        'phone_number': phone_number,
        'calling_line_name': calling_line_name,
        'org_id': org_id,
    }
    log('before_read', {'before': before})
    log('update_request', request)

    batch_job_id = api.telephony.location.update(location_id=location_id, settings=settings, org_id=org_id)
    after = model_to_dict(api.telephony.location.details(location_id=location_id, org_id=org_id))
    result = {
        'status': 'success',
        'api_response': {'before': before, 'after': after, 'request': request, 'batch_job_id': batch_job_id},
    }
    log('update_response', result)
    return result


def main() -> None:
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Añadir/actualizar cabecera de ubicación (calling_line_id.phone_number)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--location-id', required=True)
    parser.add_argument('--phone-number', required=True)
    parser.add_argument('--calling-line-name', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = actualizar_cabecera_ubicacion(
        token=get_token(args.token),
        location_id=args.location_id,
        phone_number=args.phone_number,
        org_id=args.org_id,
        calling_line_name=args.calling_line_name,
    )
    print(payload)


if __name__ == '__main__':
    main()
