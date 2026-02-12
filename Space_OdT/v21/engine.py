from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from typing import Any

from .io import (
    bootstrap_v21_inputs,
    load_locations,
    load_policy,
    load_users,
    load_workspaces,
    save_json,
    write_plan_csv,
)
from .models import EntityType, PlannedAction, RunSummary, Stage


class MissingV21InputsError(RuntimeError):
    """Raised when required v2.1 input templates were generated."""


class V21Runner:
    def __init__(self, *, token: str, out_dir: Path):
        self.token = token
        self.out_dir = out_dir

    async def run(self, *, dry_run: bool = True) -> dict[str, Any]:
        v21_dir = self.out_dir / 'v21'
        created = bootstrap_v21_inputs(v21_dir)
        if created:
            created_lines = '\n'.join(f'  - {path}' for path in created)
            raise MissingV21InputsError(
                'Se crearon plantillas requeridas para v2.1. Completá los archivos y reintentá:\n'
                f'{created_lines}'
            )

        policy = load_policy(v21_dir / 'static_policy.json')
        locations = load_locations(v21_dir / 'input_locations.csv')
        users = load_users(v21_dir / 'input_users.csv')
        workspaces = load_workspaces(v21_dir / 'input_workspaces.csv')

        actions = self._build_plan(locations=locations, users=users, workspaces=workspaces, policy=policy)

        run_id = str(uuid.uuid4())
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        mode = 'dry_run' if dry_run else 'apply'

        if not dry_run:
            # Base v2.1: mantiene el motor y la estructura de etapas.
            # La aplicación de cambios será incremental por endpoint según validación en entorno real.
            # En esta primera entrega se ejecuta como no-op controlado.
            pass

        plan_rows = [
            {
                'entity_type': a.entity_type.value,
                'entity_key': a.entity_key,
                'stage': a.stage.value,
                'mode': a.mode,
                'details': a.details,
            }
            for a in actions
        ]
        write_plan_csv(v21_dir / 'plan.csv', plan_rows)

        summary = RunSummary(
            run_id=run_id,
            mode=mode,
            completed_count=len(actions),
            failed_count=0,
            planned_count=len(actions),
            outputs={
                'plan_csv': str(v21_dir / 'plan.csv'),
                'run_state': str(v21_dir / 'run_state.json'),
            },
        )

        save_json(
            v21_dir / 'run_state.json',
            {
                'run_id': run_id,
                'executed_at': now,
                'mode': mode,
                'policy': policy,
                'completed_count': summary.completed_count,
                'failed_count': summary.failed_count,
                'planned_count': summary.planned_count,
                'planned_actions': plan_rows,
            },
        )
        return summary.__dict__

    def _build_plan(self, *, locations, users, workspaces, policy: dict[str, Any]) -> list[PlannedAction]:
        actions: list[PlannedAction] = []

        for location in locations:
            location_key = location.location_id or location.location_name
            outgoing = location.default_outgoing_profile or policy.get('default_outgoing_profile') or 'profile_2'
            actions.extend(
                [
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_CREATE_AND_ACTIVATE, 'manual_closure', 'Crear/activar sede y preparar Webex Calling'),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_ROUTE_GROUP_RESOLVE, 'manual_closure', 'Resolver routeGroupId requerido para PSTN'),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_PSTN_CONFIGURE, 'manual_closure', 'Configurar PSTN en sede'),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_NUMBERS_ADD_DISABLED, 'manual_closure', 'Alta de DDI en estado desactivado'),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_MAIN_DDI_ASSIGN, 'manual_closure', 'Asignar DDI cabecera a la sede'),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_INTERNAL_CALLING_CONFIG, 'manual_closure', 'Configurar llamadas internas'),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_OUTGOING_PERMISSION_DEFAULT, 'manual_closure', f'Aplicar perfil saliente por defecto: {outgoing}'),
                ]
            )

        for user in users:
            user_key = user.user_id or user.user_email
            actions.extend(
                [
                    PlannedAction(EntityType.USER, user_key, Stage.USER_LEGACY_INTERCOM_SECONDARY, 'manual_closure', 'Agregar intercom legacy secundario'),
                    PlannedAction(EntityType.USER, user_key, Stage.USER_LEGACY_FORWARD_PREFIX_53, 'manual_closure', 'Configurar desvío legacy con prefijo 53'),
                ]
            )
            if user.outgoing_profile:
                actions.append(
                    PlannedAction(
                        EntityType.USER,
                        user_key,
                        Stage.USER_OUTGOING_PERMISSION_OVERRIDE,
                        'manual_closure',
                        f'Aplicar perfil saliente no-default: {user.outgoing_profile}',
                    )
                )

        for workspace in workspaces:
            workspace_key = workspace.workspace_id or workspace.workspace_name
            actions.extend(
                [
                    PlannedAction(EntityType.WORKSPACE, workspace_key, Stage.WORKSPACE_LEGACY_INTERCOM_SECONDARY, 'manual_closure', 'Agregar intercom legacy secundario'),
                    PlannedAction(EntityType.WORKSPACE, workspace_key, Stage.WORKSPACE_LEGACY_FORWARD_PREFIX_53, 'manual_closure', 'Configurar desvío legacy con prefijo 53'),
                ]
            )
            if workspace.outgoing_profile:
                actions.append(
                    PlannedAction(
                        EntityType.WORKSPACE,
                        workspace_key,
                        Stage.WORKSPACE_OUTGOING_PERMISSION_OVERRIDE,
                        'manual_closure',
                        f'Aplicar perfil saliente no-default: {workspace.outgoing_profile}',
                    )
                )

        return actions
