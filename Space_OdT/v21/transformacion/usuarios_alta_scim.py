from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.scim.users import EmailObject, EmailObjectType, NameObject, SCHEMAS, ScimUser

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'usuarios_alta_scim'


def alta_usuario_scim(
    *,
    token: str,
    org_id: str,
    email: str,
    first_name: str,
    last_name: str,
    active: bool = True,
    display_name: str | None = None,
) -> dict[str, Any]:
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    filter_expr = f'userName eq "{email}"'
    search = api.scim.users.search(org_id=org_id, filter=filter_expr, count=1)
    existing = [model_to_dict(item) for item in (search.resources or [])]
    if existing:
        # 5) Resultado normalizado para logs/pipelines aguas abajo.
        result = {
            'status': 'skipped',
            'reason': 'user_already_exists',
            'api_response': {'existing': existing},
        }
        log('create_skipped', {'email': email, 'existing_count': len(existing), 'org_id': org_id})
        return result

    user = ScimUser(
        schemas=SCHEMAS,
        user_name=email,
        active=active,
        display_name=display_name or f'{first_name} {last_name}'.strip(),
        emails=[EmailObject(value=email, type=EmailObjectType.work, primary=True)],
        name=NameObject(given_name=first_name, family_name=last_name),
    )
    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {'org_id': org_id, 'settings': model_to_dict(user)}
    log('create_request', request)

    created = api.scim.users.create(org_id=org_id, user=user)
    created_payload = model_to_dict(created)
    result = {'status': 'success', 'api_response': {'request': request, 'created': created_payload}}
    log('create_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Alta de usuario vía SCIM v2 (SDK-first)')
    parser.add_argument('--token', default=None)
    parser.add_argument('--org-id', required=True)
    parser.add_argument('--email', required=True)
    parser.add_argument('--first-name', required=True)
    parser.add_argument('--last-name', required=True)
    parser.add_argument('--display-name', default=None)
    parser.add_argument('--inactive', action='store_true', help='Crear usuario como inactivo')
    args = parser.parse_args()

    payload = alta_usuario_scim(
        token=get_token(args.token),
        org_id=args.org_id,
        email=args.email,
        first_name=args.first_name,
        last_name=args.last_name,
        display_name=args.display_name,
        active=not args.inactive,
    )
    print(payload)


if __name__ == '__main__':
    main()
