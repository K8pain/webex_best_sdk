from __future__ import annotations

import argparse
import json

from wxc_sdk.telephony.location.numbers import TelephoneNumberType

from .common import get_token, load_runtime_env
from .ubicacion_actualizar_cabecera import actualizar_cabecera_ubicacion
from .ubicacion_alta_numeraciones_desactivadas import alta_numeraciones_desactivadas
from .ubicacion_configurar_pstn import configurar_pstn_ubicacion


def main() -> None:
    load_runtime_env()
    parser = argparse.ArgumentParser(description='Launcher real SDK para flujo Ubicación v2.1')
    parser.add_argument('--token', default=None)
    parser.add_argument('--location-id', required=True)
    parser.add_argument('--premise-route-id', required=True)
    parser.add_argument('--premise-route-type', default='ROUTE_GROUP', choices=['ROUTE_GROUP', 'TRUNK'])
    parser.add_argument('--phone-number', action='append', required=True, dest='phone_numbers')
    parser.add_argument('--header-phone-number', required=True)
    parser.add_argument('--header-name', default=None)
    parser.add_argument('--number-type', default='DID', choices=['DID', 'TOLLFREE', 'MOBILE'])
    parser.add_argument('--org-id', default=None)
    args = parser.parse_args()

    token = get_token(args.token)

    report = {
        'configurar_pstn': configurar_pstn_ubicacion(
            token=token,
            location_id=args.location_id,
            premise_route_type=args.premise_route_type,
            premise_route_id=args.premise_route_id,
            org_id=args.org_id,
        ),
        'alta_numeraciones_desactivadas': alta_numeraciones_desactivadas(
            token=token,
            location_id=args.location_id,
            phone_numbers=args.phone_numbers,
            number_type=TelephoneNumberType(args.number_type),
            org_id=args.org_id,
        ),
        'actualizar_cabecera': actualizar_cabecera_ubicacion(
            token=token,
            location_id=args.location_id,
            phone_number=args.header_phone_number,
            calling_line_name=args.header_name,
            org_id=args.org_id,
        ),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
