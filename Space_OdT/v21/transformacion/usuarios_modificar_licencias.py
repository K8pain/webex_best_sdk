from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.licenses import LicenseProperties, LicenseRequest, LicenseRequestOperation

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'usuarios_modificar_licencias'


def modificar_licencias_usuario(
    *,
    token: str,
    person_id: str,
    add_license_ids: list[str] | None = None,
    remove_license_ids: list[str] | None = None,
    location_id: str | None = None,
    extension: str | None = None,
    phone_number: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    if not add_license_ids and not remove_license_ids:
        raise ValueError('Se requiere al menos una licencia en add_license_ids o remove_license_ids')

    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    license_requests: list[LicenseRequest] = []
    for license_id in add_license_ids or []:
        props = None
        if any([location_id, extension, phone_number]):
            props = LicenseProperties(location_id=location_id, extension=extension, phone_number=phone_number)
        license_requests.append(
            LicenseRequest(id=license_id, operation=LicenseRequestOperation.add, properties=props)
        )
    for license_id in remove_license_ids or []:
        license_requests.append(LicenseRequest(id=license_id, operation=LicenseRequestOperation.remove))

    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'person_id': person_id,
        'org_id': org_id,
        'licenses': [model_to_dict(item) for item in license_requests],
    }
    log('licenses_request', request)

    response = api.licenses.assign_licenses_to_users(person_id=person_id, licenses=license_requests, org_id=org_id)
    response_payload = model_to_dict(response)
    # 5) Resultado normalizado para logs/pipelines aguas abajo.
    result = {'status': 'success', 'api_response': {'request': request, 'response': response_payload}}
    log('licenses_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Modificar licencias de usuario (SDK-first)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--person-id', required=True)
    parser.add_argument('--add-license-id', action='append', default=None, dest='add_license_ids')
    parser.add_argument('--remove-license-id', action='append', default=None, dest='remove_license_ids')
    parser.add_argument('--location-id', default=None)
    parser.add_argument('--extension', default=None)
    parser.add_argument('--phone-number', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = modificar_licencias_usuario(
        token=get_token(args.token),
        person_id=args.person_id,
        add_license_ids=args.add_license_ids,
        remove_license_ids=args.remove_license_ids,
        location_id=args.location_id,
        extension=args.extension,
        phone_number=args.phone_number,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
