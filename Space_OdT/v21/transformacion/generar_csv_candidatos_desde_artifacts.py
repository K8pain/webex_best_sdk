from __future__ import annotations

"""Genera CSV v21 con columnas=parámetros y valores extraídos de artifacts actuales."""

import argparse
import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPORTS_DIR = REPO_ROOT / '.artifacts' / 'exports'
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


def _split_semicolon_list(value: str | None) -> list[str]:
    raw = (value or '').strip()
    if not raw:
        return []
    return [item for item in (part.strip() for part in raw.split(';')) if item]


def _serialize_csv_value(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _parameter_columns() -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for script_name in sorted(SCRIPT_DEPENDENCIES):
        for param in SCRIPT_DEPENDENCIES[script_name]:
            if param not in seen:
                seen.add(param)
                ordered.append(param)
    return ordered


def build_parameter_row(exports_dir: Path) -> tuple[list[str], dict[str, Any]]:
    locations = _read_csv(exports_dir / 'locations.csv')
    people = _read_csv(exports_dir / 'people.csv')
    workspaces = _read_csv(exports_dir / 'workspaces.csv')
    licenses = _read_csv(exports_dir / 'licenses.csv')
    person_numbers = _read_csv(exports_dir / 'person_numbers.csv')
    person_transfer_numbers = _read_csv(exports_dir / 'person_transfer_numbers.csv')
    pstn_connections = _read_csv(exports_dir / 'location_pstn_connection.csv')

    first_person = people[0] if people else {}
    first_workspace = workspaces[0] if workspaces else {}

    phone_number = _first_non_empty(person_transfer_numbers, 'id') or _first_non_empty(person_numbers, 'id')
    row: dict[str, Any] = {
        'location_id': _first_non_empty(locations, 'location_id') or _first_non_empty(people, 'location_id'),
        'org_id': _first_non_empty(locations, 'org_id'),
        'person_id': _first_non_empty(people, 'person_id'),
        'workspace_id': _first_non_empty(workspaces, 'workspace_id'),
        'phone_number': phone_number,
        'phone_numbers': [r['id'] for r in person_numbers if (r.get('id') or '').strip()],
        'legacy_phone_number': phone_number,
        'destination': phone_number,
        'extension': _first_non_empty(person_numbers, 'name'),
        'premise_route_id': _first_non_empty(pstn_connections, 'id'),
        'premise_route_type': None,
        'enable_unknown_extension_route_policy': None,
        'email': (first_person.get('email') or '').strip() or None,
        'first_name': None,
        'last_name': None,
        'licenses': _split_semicolon_list(first_person.get('licenses')),
        'add_license_ids': [r['license_id'] for r in licenses if (r.get('license_id') or '').strip()][:2],
        'display_name': (first_workspace.get('name') or first_person.get('display_name') or '').strip() or None,
    }

    columns = _parameter_columns()
    return columns, {col: row.get(col) for col in columns}


def main() -> None:
    parser = argparse.ArgumentParser(description='Genera CSV v21 (columnas=parámetros) desde artifacts actuales')
    parser.add_argument('--exports-dir', type=Path, default=EXPORTS_DIR)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    columns, raw_row = build_parameter_row(args.exports_dir)
    row = {key: _serialize_csv_value(value) for key, value in raw_row.items()}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerow(row)

    populated = sum(1 for value in row.values() if value.strip())
    print(f'CSV generado: {args.output} ({populated}/{len(columns)} columnas con valor)')


if __name__ == '__main__':
    main()
