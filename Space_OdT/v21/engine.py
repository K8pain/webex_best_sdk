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

    @property
    def v21_dir(self) -> Path:
        return self.out_dir / 'v21'

    def _ensure_inputs(self) -> None:
        created = bootstrap_v21_inputs(self.v21_dir)
        if created:
            created_lines = '\n'.join(f'  - {path}' for path in created)
            raise MissingV21InputsError(
                'Se crearon plantillas requeridas para v2.1. Completá los archivos y reintentá:\n'
                f'{created_lines}'
            )

    def load_plan_rows(self) -> list[dict[str, Any]]:
        self._ensure_inputs()
        policy = load_policy(self.v21_dir / 'static_policy.json')
        locations = load_locations(self.v21_dir / 'input_locations.csv')
        users = load_users(self.v21_dir / 'input_users.csv')
        workspaces = load_workspaces(self.v21_dir / 'input_workspaces.csv')
        actions = self._build_plan(locations=locations, users=users, workspaces=workspaces, policy=policy)
        return [
            {
                'action_id': idx,
                'entity_type': a.entity_type.value,
                'entity_key': a.entity_key,
                'stage': a.stage.value,
                'mode': a.mode,
                'details': a.details,
            }
            for idx, a in enumerate(actions)
        ]

    async def run(self, *, dry_run: bool = True) -> dict[str, Any]:
        plan_rows = self.load_plan_rows()
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        run_id = str(uuid.uuid4())
        mode = 'dry_run' if dry_run else 'apply'

        write_plan_csv(self.v21_dir / 'plan.csv', plan_rows)
        run_state = {
            'run_id': run_id,
            'executed_at': now,
            'mode': mode,
            'completed_count': len(plan_rows),
            'failed_count': 0,
            'planned_count': len(plan_rows),
            'planned_actions': plan_rows,
        }
        save_json(self.v21_dir / 'run_state.json', run_state)

        summary = RunSummary(
            run_id=run_id,
            mode=mode,
            completed_count=len(plan_rows),
            failed_count=0,
            planned_count=len(plan_rows),
            outputs={
                'plan_csv': str(self.v21_dir / 'plan.csv'),
                'run_state': str(self.v21_dir / 'run_state.json'),
            },
        )
        return summary.__dict__

    def run_single_action(self, action_id: int, *, apply: bool) -> dict[str, Any]:
        plan_rows = self.load_plan_rows()
        if action_id < 0 or action_id >= len(plan_rows):
            raise ValueError(f'action_id out of range: {action_id}')

        action = plan_rows[action_id]
        state_path = self.v21_dir / 'action_state.json'
        if state_path.exists():
            import json
            action_state = json.loads(state_path.read_text(encoding='utf-8'))
        else:
            action_state = {'items': {}}

        key = str(action_id)
        before = action_state['items'].get(key, {'status': 'pending', 'last_executed_at': None, 'notes': ''})
        after = {
            'status': 'applied' if apply else 'previewed',
            'last_executed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'notes': f"{action['stage']} sobre {action['entity_key']}",
        }
        action_state['items'][key] = after
        save_json(state_path, action_state)

        return {
            'action': action,
            'before': before,
            'after': after,
            'changed': before != after,
        }

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
                    PlannedAction(EntityType.USER, user_key, Stage.USER_OUTGOING_PERMISSION_OVERRIDE, 'manual_closure', f'Aplicar perfil saliente no-default: {user.outgoing_profile}')
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
                    PlannedAction(EntityType.WORKSPACE, workspace_key, Stage.WORKSPACE_OUTGOING_PERMISSION_OVERRIDE, 'manual_closure', f'Aplicar perfil saliente no-default: {workspace.outgoing_profile}')
                )

        return actions
