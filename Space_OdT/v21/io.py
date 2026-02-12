from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .models import LocationInput, UserInput, WorkspaceInput

LOCATION_HEADERS = [
    'location_name',
    'location_id',
    'org_id',
    'country_code',
    'time_zone',
    'language_code',
    'address_line1',
    'address_line2',
    'city',
    'state',
    'postal_code',
    'route_group_id',
    'main_number',
    'default_outgoing_profile',
]

USER_HEADERS = [
    'user_email',
    'user_id',
    'location_id',
    'location_name',
    'extension',
    'legacy_secondary_number',
    'legacy_forward_target',
    'outgoing_profile',
]

WORKSPACE_HEADERS = [
    'workspace_name',
    'workspace_id',
    'location_id',
    'location_name',
    'extension',
    'legacy_secondary_number',
    'legacy_forward_target',
    'outgoing_profile',
]


def bootstrap_v21_inputs(v21_dir: Path) -> list[Path]:
    v21_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    paths = {
        'input_locations.csv': LOCATION_HEADERS,
        'input_users.csv': USER_HEADERS,
        'input_workspaces.csv': WORKSPACE_HEADERS,
    }
    for file_name, headers in paths.items():
        path = v21_dir / file_name
        if not path.exists():
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(headers)
            created.append(path)

    policy = v21_dir / 'static_policy.json'
    if not policy.exists():
        policy.write_text(
            json.dumps(
                {
                    'default_outgoing_profile': 'profile_2',
                    'legacy_forward_prefix': '53',
                    'manual_tasks_enabled': True,
                },
                indent=2,
                ensure_ascii=False,
            )
            + '\n',
            encoding='utf-8',
        )
        created.append(policy)

    out_of_scope = v21_dir / 'OUT_OF_SCOPE.md'
    if not out_of_scope.exists():
        out_of_scope.write_text(_out_of_scope_text(), encoding='utf-8')
        created.append(out_of_scope)

    return created


def _out_of_scope_text() -> str:
    return """# Fuera de scope (v2.1)

Estas tareas se gestionarán por carga masiva en Control Hub y no forman parte del script v2.1:

- Alta/Modificación/Supresión usuarios
- Asignar permisos de llamadas
- Traslado de usuarios a otro CUV
- Crear Grupos de usuarios
- Añadir/Editar Ubicaciones
- Eliminar Ubicaciones
- Añadir Espacios de trabajo (Workspace)
- Modificar/Eliminar Espacios de trabajo
- Alta/Modificación contactos Webex
- Alta/Modificar los grupos de recepción de llamadas
- Agregar locuciones
- Alta/Modificar el asistente automático
- Alta/modificar las extensiones de detención de llamada
- Alta/modificar los grupos de llamadas en espera
- Alta/Modificación de Grupo de búsqueda
- Alta de Colas
- Modificación de Colas
- Agregar DDIs
- Asignar DDIs

Nota operativa: algunas actividades se inician por carga masiva en Control Hub y requieren tareas manuales posteriores para completar el cierre. El objetivo de v2.1 es cubrir precisamente esas tareas manuales de cierre donde aplica.
"""


def load_policy(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def _normalize_phone(value: str | None) -> str | None:
    raw = (value or '').strip()
    if not raw:
        return None
    if raw.startswith('+') and raw[1:].isdigit():
        return raw
    if raw.isdigit():
        return f'+{raw}'
    raise ValueError(f'invalid phone number: {value}')


def load_locations(path: Path) -> list[LocationInput]:
    rows = _read_csv(path)
    data: list[LocationInput] = []
    for row_number, row in enumerate(rows, start=2):
        location_name = (row.get('location_name') or '').strip()
        if not location_name:
            raise ValueError(f'row {row_number}: location_name is required')
        data.append(
            LocationInput(
                row_number=row_number,
                location_name=location_name,
                location_id=(row.get('location_id') or '').strip() or None,
                org_id=(row.get('org_id') or '').strip() or None,
                route_group_id=(row.get('route_group_id') or '').strip() or None,
                main_number=_normalize_phone(row.get('main_number')),
                default_outgoing_profile=(row.get('default_outgoing_profile') or '').strip() or None,
                payload={k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()},
            )
        )
    return data


def load_users(path: Path) -> list[UserInput]:
    rows = _read_csv(path)
    data: list[UserInput] = []
    for row_number, row in enumerate(rows, start=2):
        user_email = (row.get('user_email') or '').strip().lower()
        if not user_email:
            raise ValueError(f'row {row_number}: user_email is required')
        data.append(
            UserInput(
                row_number=row_number,
                user_email=user_email,
                user_id=(row.get('user_id') or '').strip() or None,
                location_id=(row.get('location_id') or '').strip() or None,
                location_name=(row.get('location_name') or '').strip() or None,
                extension=(row.get('extension') or '').strip() or None,
                legacy_secondary_number=_normalize_phone(row.get('legacy_secondary_number')),
                legacy_forward_target=_normalize_phone(row.get('legacy_forward_target')),
                outgoing_profile=(row.get('outgoing_profile') or '').strip() or None,
                payload={k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()},
            )
        )
    return data


def load_workspaces(path: Path) -> list[WorkspaceInput]:
    rows = _read_csv(path)
    data: list[WorkspaceInput] = []
    for row_number, row in enumerate(rows, start=2):
        workspace_name = (row.get('workspace_name') or '').strip()
        if not workspace_name:
            raise ValueError(f'row {row_number}: workspace_name is required')
        data.append(
            WorkspaceInput(
                row_number=row_number,
                workspace_name=workspace_name,
                workspace_id=(row.get('workspace_id') or '').strip() or None,
                location_id=(row.get('location_id') or '').strip() or None,
                location_name=(row.get('location_name') or '').strip() or None,
                extension=(row.get('extension') or '').strip() or None,
                legacy_secondary_number=_normalize_phone(row.get('legacy_secondary_number')),
                legacy_forward_target=_normalize_phone(row.get('legacy_forward_target')),
                outgoing_profile=(row.get('outgoing_profile') or '').strip() or None,
                payload={k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()},
            )
        )
    return data


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')


def write_plan_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    headers = list(rows[0].keys())
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
