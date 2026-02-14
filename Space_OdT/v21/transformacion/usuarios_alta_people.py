from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.people import PeopleApi, Person, PhoneNumber

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'usuarios_alta_people'


def alta_usuario_people(
    *,
    token: str,
    email: str,
    first_name: str,
    last_name: str,
    display_name: str | None = None,
    location_id: str | None = None,
    extension: str | None = None,
    licenses: list[str] | None = None,
    phone_number: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)
    people_api: PeopleApi = api.people

    existing = [model_to_dict(item) for item in people_api.list(email=email, org_id=org_id)]
    if existing:
        # 5) Resultado normalizado para logs/pipelines aguas abajo.
        result = {
            'status': 'skipped',
            'reason': 'user_already_exists',
            'api_response': {'existing': existing},
        }
        log('create_skipped', {'email': email, 'existing_count': len(existing)})
        return result

    person_settings = Person(
        emails=[email],
        first_name=first_name,
        last_name=last_name,
        display_name=display_name or f'{first_name} {last_name}'.strip(),
        location_id=location_id,
        extension=extension,
        licenses=licenses,
        phone_numbers=phone_number and [PhoneNumber(value=phone_number)] or None,
    )

    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'org_id': org_id,
        'calling_data': True,
        'settings': model_to_dict(person_settings),
    }
    log('create_request', request)

    created = people_api.create(settings=person_settings, calling_data=True)
    created_payload = model_to_dict(created)

    result = {'status': 'success', 'api_response': {'request': request, 'created': created_payload}}
    log('create_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Alta de usuarios en People API (SDK-first)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--email', required=True)
    parser.add_argument('--first-name', required=True)
    parser.add_argument('--last-name', required=True)
    parser.add_argument('--display-name', default=None)
    parser.add_argument('--location-id', default=None)
    parser.add_argument('--extension', default=None)
    parser.add_argument('--license-id', action='append', default=None, dest='licenses')
    parser.add_argument('--phone-number', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = alta_usuario_people(
        token=get_token(args.token),
        email=args.email,
        first_name=args.first_name,
        last_name=args.last_name,
        display_name=args.display_name,
        location_id=args.location_id,
        extension=args.extension,
        licenses=args.licenses,
        phone_number=args.phone_number,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
