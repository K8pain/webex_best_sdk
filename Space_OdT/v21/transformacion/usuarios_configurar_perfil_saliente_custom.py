from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.person_settings.permissions_out import (
    Action,
    CallTypePermission,
    CallingPermissions,
    OutgoingPermissionCallType,
    OutgoingPermissions,
)

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'usuarios_configurar_perfil_saliente_custom'


def _normalize_call_types(raw_values: list[str] | None) -> set[OutgoingPermissionCallType]:
    values = raw_values or []
    return {OutgoingPermissionCallType(value.strip().upper()) for value in values if value.strip()}


def configurar_perfil_saliente_custom_usuario(
    *,
    token: str,
    person_id: str,
    allow_call_types: list[str] | None = None,
    block_call_types: list[str] | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """
    Configura permisos salientes custom para usuario.
    Por defecto permite todos los tipos salvo los indicados en --block-call-type.
    """
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    # 2) Snapshot previo: leemos estado actual para trazabilidad y rollback manual.
    before = model_to_dict(api.person_settings.permissions_out.read(entity_id=person_id, org_id=org_id))

    allow_set = _normalize_call_types(allow_call_types)
    block_set = _normalize_call_types(block_call_types)

    calling_permissions = CallingPermissions.allow_all()
    for call_type in block_set:
        setattr(
            calling_permissions,
            call_type.name.lower(),
            CallTypePermission(action=Action.block, transfer_enabled=False),
        )
    for call_type in allow_set:
        setattr(
            calling_permissions,
            call_type.name.lower(),
            CallTypePermission(action=Action.allow, transfer_enabled=True),
        )

    settings = OutgoingPermissions(
        use_custom_enabled=True,
        use_custom_permissions=True,
        calling_permissions=calling_permissions,
    )
    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {'entity_id': person_id, 'org_id': org_id, 'settings': model_to_dict(settings)}

    log('before_read', {'before': before})
    log('configure_request', request)

    # 4) Ejecución del cambio contra Webex Calling.
    api.person_settings.permissions_out.configure(entity_id=person_id, settings=settings, org_id=org_id)
    after = model_to_dict(api.person_settings.permissions_out.read(entity_id=person_id, org_id=org_id))

    # 5) Resultado normalizado para logs/pipelines aguas abajo.
    result = {'status': 'success', 'api_response': {'before': before, 'after': after, 'request': request}}
    log('configure_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar perfil de llamadas salientes custom para usuario')
    parser.add_argument('--token', default=None)
    parser.add_argument('--person-id', required=True)
    parser.add_argument('--allow-call-type', action='append', default=None)
    parser.add_argument('--block-call-type', action='append', default=None)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = configurar_perfil_saliente_custom_usuario(
        token=get_token(args.token),
        person_id=args.person_id,
        allow_call_types=args.allow_call_type,
        block_call_types=args.block_call_type,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
