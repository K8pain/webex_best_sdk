from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
from typing import Any

from wxc_sdk.person_settings.permissions_out import OutgoingPermissions

from .common import action_logger, create_api, get_token, load_runtime_env, model_to_dict

SCRIPT_NAME = 'ubicacion_configurar_permisos_salientes_defecto'


def configurar_permisos_salientes_defecto_ubicacion(
    *,
    token: str,
    location_id: str,
    org_id: str | None = None,
) -> dict[str, Any]:
    """
    Restablece permisos salientes de ubicación para usar configuración por defecto.
    """
    # 1) Inicialización: logger por acción y cliente API autenticado.
    log = action_logger(SCRIPT_NAME)
    api = create_api(token)

    # 2) Snapshot previo: leemos estado actual para trazabilidad y rollback manual.
    before = model_to_dict(api.telephony.location.permissions_out.read(entity_id=location_id, org_id=org_id))
    settings = OutgoingPermissions(use_custom_enabled=False, use_custom_permissions=False)
    # 3) Payload final: registramos exactamente qué se enviará al endpoint.
    request = {
        'entity_id': location_id,
        'settings': model_to_dict(settings),
        'org_id': org_id,
    }

    log('before_read', {'before': before})
    log('configure_request', request)

    # 4) Ejecución del cambio contra Webex Calling.
    api.telephony.location.permissions_out.configure(entity_id=location_id, settings=settings, org_id=org_id)
    after = model_to_dict(api.telephony.location.permissions_out.read(entity_id=location_id, org_id=org_id))

    # 5) Resultado normalizado para logs/pipelines aguas abajo.
    result = {'status': 'success', 'api_response': {'before': before, 'after': after, 'request': request}}
    log('configure_response', result)
    return result


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Configurar permisos salientes por defecto en una ubicación')
    parser.add_argument('--token', default=None)
    parser.add_argument('--location-id', required=True)
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    payload = configurar_permisos_salientes_defecto_ubicacion(
        token=get_token(args.token),
        location_id=args.location_id,
        org_id=args.org_id,
    )
    print(payload)


if __name__ == '__main__':
    main()
