from __future__ import annotations

"""Script v21 de transformación: incluye comentarios guía en secciones críticas."""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPORTS_DIR = Path('.artifacts/exports')
DEFAULT_OUTPUT = EXPORTS_DIR / 'v21_transformacion_candidatos.csv'

SCRIPT_DEPENDENCIES: dict[str, list[str]] = {
    'ubicacion_actualizar_cabecera': ['location_id', 'phone_number'],
    'ubicacion_alta_numeraciones_desactivadas': ['location_id', 'phone_numbers'],
    'ubicacion_configurar_llamadas_internas': [
        'location_id',
        'enable_unknown_extension_route_policy',
        'premise_route_id',
        'premise_route_type',
    ],
    'ubicacion_configurar_permisos_salientes_defecto': ['location_id'],
    'ubicacion_configurar_pstn': ['location_id', 'premise_route_type', 'premise_route_id'],
    'usuarios_alta_people': ['email', 'first_name', 'last_name', 'location_id', 'licenses'],
    'usuarios_alta_scim': ['org_id', 'email', 'first_name', 'last_name'],
    'usuarios_anadir_intercom_legacy': ['person_id', 'legacy_phone_number'],
    'usuarios_configurar_desvio_prefijo53': ['person_id', 'extension', 'destination'],
    'usuarios_configurar_perfil_saliente_custom': ['person_id'],
    'usuarios_modificar_licencias': ['person_id', 'add_license_ids'],
    'workspaces_alta': ['display_name', 'location_id'],
    'workspaces_anadir_intercom_legacy': ['workspace_id', 'legacy_phone_number'],
    'workspaces_configurar_desvio_prefijo53': ['workspace_id', 'extension', 'destination'],
    'workspaces_configurar_perfil_saliente_custom': ['workspace_id'],
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open('r', encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def _first_non_empty(rows: list[dict[str, str]], field: str) -> str | None:
    for row in rows:
        value = (row.get(field) or '').strip()
        if value:
            return value
    return None


def _build_params(lookups: dict[str, Any]) -> dict[str, dict[str, Any]]:
    now = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    first_license = lookups.get('license_ids', [])[:1]
    second_license = lookups.get('license_ids', [])[1:2]
    return {
        'ubicacion_actualizar_cabecera': {
            'location_id': lookups.get('location_id'),
            'phone_number': lookups.get('phone_number'),
            'calling_line_name': 'LAB Header v21',
            'org_id': lookups.get('org_id'),
        },
        'ubicacion_alta_numeraciones_desactivadas': {
            'location_id': lookups.get('location_id'),
            'phone_numbers': [lookups.get('phone_number')] if lookups.get('phone_number') else [],
            'number_type': 'DID',
            'org_id': lookups.get('org_id'),
        },
        'ubicacion_configurar_llamadas_internas': {
            'location_id': lookups.get('location_id'),
            'enable_unknown_extension_route_policy': True,
            'premise_route_id': lookups.get('premise_route_id'),
            'premise_route_type': 'ROUTE_GROUP',
            'org_id': lookups.get('org_id'),
        },
        'ubicacion_configurar_permisos_salientes_defecto': {
            'location_id': lookups.get('location_id'),
            'org_id': lookups.get('org_id'),
        },
        'ubicacion_configurar_pstn': {
            'location_id': lookups.get('location_id'),
            'premise_route_type': 'ROUTE_GROUP',
            'premise_route_id': lookups.get('premise_route_id'),
            'org_id': lookups.get('org_id'),
        },
        'usuarios_alta_people': {
            'email': f'v21.people.{now}@lab.example.com',
            'first_name': 'V21',
            'last_name': f'People{now[-6:]}',
            'display_name': f'V21 People {now[-6:]}',
            'location_id': lookups.get('location_id'),
            'licenses': first_license,
            'phone_number': None,
            'org_id': lookups.get('org_id'),
        },
        'usuarios_alta_scim': {
            'org_id': lookups.get('org_id'),
            'email': f'v21.scim.{now}@lab.example.com',
            'first_name': 'V21',
            'last_name': f'Scim{now[-6:]}',
            'active': True,
            'display_name': f'V21 Scim {now[-6:]}',
        },
        'usuarios_anadir_intercom_legacy': {
            'person_id': lookups.get('person_id'),
            'legacy_phone_number': lookups.get('phone_number'),
            'org_id': lookups.get('org_id'),
        },
        'usuarios_configurar_desvio_prefijo53': {
            'person_id': lookups.get('person_id'),
            'extension': lookups.get('extension') or '5301',
            'destination': lookups.get('phone_number'),
            'org_id': lookups.get('org_id'),
        },
        'usuarios_configurar_perfil_saliente_custom': {
            'person_id': lookups.get('person_id'),
            'allow_call_types': ['NATIONAL'],
            'block_call_types': ['INTERNATIONAL'],
            'org_id': lookups.get('org_id'),
        },
        'usuarios_modificar_licencias': {
            'person_id': lookups.get('person_id'),
            'add_license_ids': second_license or first_license,
            'remove_license_ids': [],
            'location_id': lookups.get('location_id'),
            'extension': lookups.get('extension'),
            'phone_number': lookups.get('phone_number'),
            'org_id': lookups.get('org_id'),
        },
        'workspaces_alta': {
            'display_name': f'WS v21 {now[-6:]}',
            'location_id': lookups.get('location_id'),
            'org_id': lookups.get('org_id'),
        },
        'workspaces_anadir_intercom_legacy': {
            'workspace_id': lookups.get('workspace_id'),
            'legacy_phone_number': lookups.get('phone_number'),
            'org_id': lookups.get('org_id'),
        },
        'workspaces_configurar_desvio_prefijo53': {
            'workspace_id': lookups.get('workspace_id'),
            'extension': lookups.get('extension') or '5302',
            'destination': lookups.get('phone_number'),
            'org_id': lookups.get('org_id'),
        },
        'workspaces_configurar_perfil_saliente_custom': {
            'workspace_id': lookups.get('workspace_id'),
            'allow_call_types': ['NATIONAL'],
            'block_call_types': ['INTERNATIONAL'],
            'org_id': lookups.get('org_id'),
        },
    }


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ''
    if isinstance(value, list):
        return len(value) == 0 or all(_is_missing(item) for item in value)
    return False


def build_candidate_rows(exports_dir: Path) -> list[dict[str, str]]:
    locations = _read_csv(exports_dir / 'locations.csv')
    people = _read_csv(exports_dir / 'people.csv')
    workspaces = _read_csv(exports_dir / 'workspaces.csv')
    licenses = _read_csv(exports_dir / 'licenses.csv')

    lookups = {
        'location_id': _first_non_empty(locations, 'location_id'),
        'org_id': _first_non_empty(locations, 'org_id'),
        'person_id': _first_non_empty(people, 'person_id'),
        'workspace_id': _first_non_empty(workspaces, 'workspace_id'),
        'phone_number': _first_non_empty(_read_csv(exports_dir / 'person_transfer_numbers.csv'), 'id')
        or _first_non_empty(_read_csv(exports_dir / 'person_numbers.csv'), 'id'),
        'extension': _first_non_empty(_read_csv(exports_dir / 'person_numbers.csv'), 'name'),
        'premise_route_id': _first_non_empty(_read_csv(exports_dir / 'location_pstn_connection.csv'), 'id'),
        'license_ids': [row['license_id'] for row in licenses if row.get('license_id')],
    }

    params_by_script = _build_params(lookups)
    rows: list[dict[str, str]] = []
    for script_name in sorted(SCRIPT_DEPENDENCIES):
        required = SCRIPT_DEPENDENCIES[script_name]
        params = params_by_script[script_name]
        missing = [dep for dep in required if _is_missing(params.get(dep))]
        rows.append(
            {
                'script_name': script_name,
                'candidate_status': 'ready' if not missing else 'missing_dependencies',
                'required_dependencies': ';'.join(required),
                'missing_dependencies': ';'.join(missing),
                'params_json': json.dumps(params, ensure_ascii=False, sort_keys=True),
                'artifact_sources': 'locations.csv;people.csv;workspaces.csv;licenses.csv;person_numbers.csv;person_transfer_numbers.csv;location_pstn_connection.csv',
                'notes': 'Generado automáticamente desde lookups de .artifacts/exports',
            }
        )
    return rows


def main() -> None:
    # Entrada CLI: carga entorno, parsea argumentos y ejecuta la acción.
    parser = argparse.ArgumentParser(description='Genera CSV de candidatos v21 en base a .artifacts/exports')
    parser.add_argument('--exports-dir', type=Path, default=EXPORTS_DIR)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = build_candidate_rows(args.exports_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                'script_name',
                'candidate_status',
                'required_dependencies',
                'missing_dependencies',
                'params_json',
                'artifact_sources',
                'notes',
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    ready = sum(1 for row in rows if row['candidate_status'] == 'ready')
    print(f'CSV generado: {args.output} ({ready}/{len(rows)} scripts con dependencias completas)')


if __name__ == '__main__':
    main()
