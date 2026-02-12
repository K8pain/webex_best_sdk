from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from wxc_sdk.common import NumberState, RouteIdentity, RouteType
from wxc_sdk.locations import Location, LocationAddress
from wxc_sdk.person_settings.forwarding import CallForwardingAlways
from wxc_sdk.person_settings.numbers import UpdatePersonNumbers, UpdatePersonPhoneNumber
from wxc_sdk.person_settings.permissions_out import OutgoingPermissions
from wxc_sdk.telephony.location import CallingLineId, TelephonyLocation
from wxc_sdk.telephony.location.internal_dialing import InternalDialing
from wxc_sdk.telephony.location.numbers import TelephoneNumberType
from wxc_sdk.workspace_settings.numbers import UpdateWorkspacePhoneNumber

from Space_OdT.sdk_client import create_api

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

    def _load_all(self) -> tuple[dict[str, Any], list, list, list]:
        self._ensure_inputs()
        policy = load_policy(self.v21_dir / 'static_policy.json')
        locations = load_locations(self.v21_dir / 'input_locations.csv')
        users = load_users(self.v21_dir / 'input_users.csv')
        workspaces = load_workspaces(self.v21_dir / 'input_workspaces.csv')
        return policy, locations, users, workspaces

    def load_plan_rows(self) -> list[dict[str, Any]]:
        policy, locations, users, workspaces = self._load_all()
        actions = self._build_plan(locations=locations, users=users, workspaces=workspaces, policy=policy)
        return [
            {
                'action_id': idx,
                'entity_type': a.entity_type.value,
                'entity_key': a.entity_key,
                'stage': a.stage.value,
                'mode': a.mode,
                'details': a.details,
                'payload': a.payload,
            }
            for idx, a in enumerate(actions)
        ]

    async def run(self, *, dry_run: bool = True) -> dict[str, Any]:
        plan_rows = self.load_plan_rows()
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        run_id = str(uuid.uuid4())
        mode = 'dry_run' if dry_run else 'apply'

        results: list[dict[str, Any]] = []
        if not dry_run:
            for row in plan_rows:
                results.append(self.run_single_action(int(row['action_id']), apply=True))

        write_plan_csv(self.v21_dir / 'plan.csv', plan_rows)
        run_state = {
            'run_id': run_id,
            'executed_at': now,
            'mode': mode,
            'completed_count': len(plan_rows),
            'failed_count': sum(1 for r in results if r.get('error')),
            'planned_count': len(plan_rows),
            'planned_actions': plan_rows,
            'results': results,
        }
        save_json(self.v21_dir / 'run_state.json', run_state)

        summary = RunSummary(
            run_id=run_id,
            mode=mode,
            completed_count=len(plan_rows),
            failed_count=run_state['failed_count'],
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
        stage = Stage(action['stage'])

        state_path = self.v21_dir / 'action_state.json'
        action_state = {'items': {}}
        if state_path.exists():
            action_state = json.loads(state_path.read_text(encoding='utf-8'))

        before = self._read_current_state(action)
        after = before
        error = None

        if apply:
            try:
                self._apply_action(action)
                after = self._read_current_state(action)
            except Exception as exc:  # pragma: no cover - remote/network dependent
                error = str(exc)

        key = str(action_id)
        action_state['items'][key] = {
            'stage': stage.value,
            'entity_key': action['entity_key'],
            'status': 'failed' if error else ('applied' if apply else 'previewed'),
            'last_executed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'error': error,
        }
        save_json(state_path, action_state)

        return {
            'action': action,
            'before': before,
            'after': after,
            'changed': before != after,
            'error': error,
        }

    def _read_current_state(self, action: dict[str, Any]) -> Any:
        stage = Stage(action['stage'])
        payload = action.get('payload') or {}
        with create_api(token=self.token) as api:
            if stage == Stage.LOCATION_CREATE_AND_ACTIVATE:
                location_id = self._resolve_location_id(api, payload)
                if not location_id:
                    return {'location': None, 'calling': None}
                return {
                    'location': self._safe_model(api.locations.details(location_id=location_id)),
                    'calling': self._safe_model(api.telephony.location.details(location_id=location_id)),
                }
            if stage == Stage.LOCATION_ROUTE_GROUP_RESOLVE:
                route_group_id = self._resolve_route_group_id(api, payload)
                return {'route_group_id': route_group_id}
            if stage == Stage.LOCATION_PSTN_CONFIGURE:
                location_id = self._require_location_id(api, payload)
                return {'pstn_options': [self._safe_model(x) for x in api.telephony.pstn.list(location_id=location_id)]}
            if stage == Stage.LOCATION_NUMBERS_ADD_DISABLED:
                location_id = self._require_location_id(api, payload)
                numbers = [n for n in api.telephony.location.phone_numbers(location_id=location_id)]
                return {'numbers': [self._safe_model(n) for n in numbers]}
            if stage == Stage.LOCATION_MAIN_DDI_ASSIGN:
                location_id = self._require_location_id(api, payload)
                return self._safe_model(api.telephony.location.details(location_id=location_id))
            if stage == Stage.LOCATION_INTERNAL_CALLING_CONFIG:
                location_id = self._require_location_id(api, payload)
                return self._safe_model(api.telephony.location.internal_dialing.read(location_id=location_id))
            if stage == Stage.LOCATION_OUTGOING_PERMISSION_DEFAULT:
                location_id = self._require_location_id(api, payload)
                return self._safe_model(api.telephony.permissions_out.read(entity_id=location_id))
            if stage in {Stage.USER_LEGACY_INTERCOM_SECONDARY, Stage.USER_LEGACY_FORWARD_PREFIX_53, Stage.USER_OUTGOING_PERMISSION_OVERRIDE}:
                person_id = self._resolve_person_id(api, payload)
                if not person_id:
                    return {'person': None}
                if stage == Stage.USER_LEGACY_INTERCOM_SECONDARY:
                    return self._safe_model(api.person_settings.numbers.read(person_id=person_id))
                if stage == Stage.USER_LEGACY_FORWARD_PREFIX_53:
                    return self._safe_model(api.person_settings.forwarding.read(entity_id=person_id))
                return self._safe_model(api.person_settings.permissions_out.read(entity_id=person_id))
            if stage in {Stage.WORKSPACE_LEGACY_INTERCOM_SECONDARY, Stage.WORKSPACE_LEGACY_FORWARD_PREFIX_53, Stage.WORKSPACE_OUTGOING_PERMISSION_OVERRIDE}:
                workspace_id = self._resolve_workspace_id(api, payload)
                if not workspace_id:
                    return {'workspace': None}
                if stage == Stage.WORKSPACE_LEGACY_INTERCOM_SECONDARY:
                    return self._safe_model(api.workspace_settings.numbers.read(workspace_id=workspace_id))
                if stage == Stage.WORKSPACE_LEGACY_FORWARD_PREFIX_53:
                    return self._safe_model(api.workspace_settings.forwarding.read(entity_id=workspace_id))
                return self._safe_model(api.workspace_settings.permissions_out.read(entity_id=workspace_id))
        return {'info': 'no_state_reader'}

    def _apply_action(self, action: dict[str, Any]) -> None:
        stage = Stage(action['stage'])
        payload = action.get('payload') or {}
        with create_api(token=self.token) as api:
            if stage == Stage.LOCATION_CREATE_AND_ACTIVATE:
                self._apply_location_create_and_activate(api, payload)
                return
            if stage == Stage.LOCATION_ROUTE_GROUP_RESOLVE:
                self._resolve_route_group_id(api, payload)
                return
            if stage == Stage.LOCATION_PSTN_CONFIGURE:
                location_id = self._require_location_id(api, payload)
                route_group_id = self._require_route_group_id(api, payload)
                api.telephony.pstn.configure(
                    location_id=location_id,
                    premise_route_type='ROUTE_GROUP',
                    premise_route_id=route_group_id,
                    org_id=payload.get('org_id') or None,
                )
                return
            if stage == Stage.LOCATION_NUMBERS_ADD_DISABLED:
                location_id = self._require_location_id(api, payload)
                numbers = self._split_pipe(payload.get('location_numbers'))
                if numbers:
                    api.telephony.location.numbers.add(
                        location_id=location_id,
                        phone_numbers=numbers,
                        number_type=TelephoneNumberType.did,
                        state=NumberState.inactive,
                        org_id=payload.get('org_id') or None,
                    )
                return
            if stage == Stage.LOCATION_MAIN_DDI_ASSIGN:
                location_id = self._require_location_id(api, payload)
                main_number = payload.get('main_number')
                if not main_number:
                    return
                current = api.telephony.location.details(location_id=location_id, org_id=payload.get('org_id') or None)
                update = TelephonyLocation(
                    calling_line_id=CallingLineId(
                        name=(current.calling_line_id.name if current.calling_line_id else current.name),
                        phone_number=main_number,
                    )
                )
                api.telephony.location.update(location_id=location_id, settings=update, org_id=payload.get('org_id') or None)
                return
            if stage == Stage.LOCATION_INTERNAL_CALLING_CONFIG:
                location_id = self._require_location_id(api, payload)
                enabled = payload.get('internal_dialing_enabled')
                if enabled is None:
                    return
                if enabled:
                    route_id = payload.get('unknown_extension_route_id') or self._require_route_group_id(api, payload)
                    route_type = payload.get('unknown_extension_route_type') or 'ROUTE_GROUP'
                    route_name = payload.get('unknown_extension_route_name')
                    route_identity = RouteIdentity(id=route_id, route_type=RouteType(route_type), name=route_name)
                else:
                    route_identity = None
                api.telephony.location.internal_dialing.update(
                    location_id=location_id,
                    update=InternalDialing(
                        enable_unknown_extension_route_policy=bool(enabled),
                        unknown_extension_route_identity=route_identity,
                    ),
                    org_id=payload.get('org_id') or None,
                )
                return
            if stage == Stage.LOCATION_OUTGOING_PERMISSION_DEFAULT:
                location_id = self._require_location_id(api, payload)
                settings = self._outgoing_profile_settings(payload=payload)
                api.telephony.permissions_out.configure(
                    entity_id=location_id,
                    settings=OutgoingPermissions.model_validate(settings),
                    org_id=payload.get('org_id') or None,
                )
                return
            if stage == Stage.USER_LEGACY_INTERCOM_SECONDARY:
                person_id = self._resolve_person_id(api, payload)
                number = payload.get('legacy_secondary_number')
                if person_id and number:
                    api.person_settings.numbers.update(
                        person_id=person_id,
                        update=UpdatePersonNumbers(phone_numbers=[UpdatePersonPhoneNumber(action='ADD', direct_number=number)]),
                    )
                return
            if stage == Stage.USER_LEGACY_FORWARD_PREFIX_53:
                person_id = self._resolve_person_id(api, payload)
                if person_id:
                    destination = self._legacy_target(payload)
                    if destination:
                        current = api.person_settings.forwarding.read(entity_id=person_id)
                        current.call_forwarding.always = CallForwardingAlways(enabled=True, destination=destination, destination_voicemail_enabled=False, ring_reminder_enabled=False)
                        api.person_settings.forwarding.configure(entity_id=person_id, forwarding=current)
                return
            if stage == Stage.USER_OUTGOING_PERMISSION_OVERRIDE:
                person_id = self._resolve_person_id(api, payload)
                if person_id:
                    settings = self._outgoing_profile_settings(payload=payload)
                    api.person_settings.permissions_out.configure(entity_id=person_id, settings=OutgoingPermissions.model_validate(settings))
                return
            if stage == Stage.WORKSPACE_LEGACY_INTERCOM_SECONDARY:
                workspace_id = self._resolve_workspace_id(api, payload)
                number = payload.get('legacy_secondary_number')
                if workspace_id and number:
                    api.workspace_settings.numbers.update(
                        workspace_id=workspace_id,
                        phone_numbers=[UpdateWorkspacePhoneNumber(action='ADD', direct_number=number)],
                    )
                return
            if stage == Stage.WORKSPACE_LEGACY_FORWARD_PREFIX_53:
                workspace_id = self._resolve_workspace_id(api, payload)
                if workspace_id:
                    destination = self._legacy_target(payload)
                    if destination:
                        current = api.workspace_settings.forwarding.read(entity_id=workspace_id)
                        current.call_forwarding.always = CallForwardingAlways(enabled=True, destination=destination, destination_voicemail_enabled=False, ring_reminder_enabled=False)
                        api.workspace_settings.forwarding.configure(entity_id=workspace_id, forwarding=current)
                return
            if stage == Stage.WORKSPACE_OUTGOING_PERMISSION_OVERRIDE:
                workspace_id = self._resolve_workspace_id(api, payload)
                if workspace_id:
                    settings = self._outgoing_profile_settings(payload=payload)
                    api.workspace_settings.permissions_out.configure(entity_id=workspace_id, settings=OutgoingPermissions.model_validate(settings))
                return

    def _apply_location_create_and_activate(self, api, payload: dict[str, Any]) -> None:
        location_id = self._resolve_location_id(api, payload)
        if location_id:
            return
        name = payload['location_name']
        org_id = payload.get('org_id') or None
        time_zone = payload.get('time_zone') or 'Europe/Madrid'
        language = payload.get('language_code') or 'es_ES'
        country = payload.get('country_code') or 'ES'
        address = LocationAddress(
            address1=payload.get('address_line1') or 'N/A',
            address2=payload.get('address_line2') or None,
            city=payload.get('city') or 'N/A',
            state=payload.get('state') or 'N/A',
            postal_code=payload.get('postal_code') or '00000',
            country=country,
        )
        location = Location(
            name=name,
            time_zone=time_zone,
            preferred_language=language,
            announcement_language=language,
            address=address,
        )
        new_location_id = api.locations.create(
            name=name,
            time_zone=time_zone,
            preferred_language=language,
            announcement_language=language,
            address1=address.address1,
            address2=address.address2,
            city=address.city,
            state=address.state,
            postal_code=address.postal_code,
            country=address.country,
            org_id=org_id,
        )
        api.telephony.location.enable_for_calling(location=location, org_id=org_id)
        payload['location_id'] = new_location_id

    def _resolve_location_id(self, api, payload: dict[str, Any]) -> str | None:
        if payload.get('location_id'):
            return payload['location_id']
        name = payload.get('location_name')
        if not name:
            return None
        location = api.locations.by_name(name=name, org_id=payload.get('org_id') or None)
        if location:
            payload['location_id'] = location.location_id
            return location.location_id
        return None

    def _require_location_id(self, api, payload: dict[str, Any]) -> str:
        location_id = self._resolve_location_id(api, payload)
        if not location_id:
            raise ValueError(f"location not found: {payload.get('location_name')}")
        return location_id

    def _resolve_route_group_id(self, api, payload: dict[str, Any]) -> str | None:
        if payload.get('route_group_id'):
            return payload['route_group_id']
        rg_name = payload.get('route_group_name')
        if not rg_name:
            return None
        for rg in api.telephony.prem_pstn.route_group.list(name=rg_name, org_id=payload.get('org_id') or None):
            if rg.name == rg_name:
                payload['route_group_id'] = rg.rg_id
                return rg.rg_id
        return None

    def _require_route_group_id(self, api, payload: dict[str, Any]) -> str:
        rg_id = self._resolve_route_group_id(api, payload)
        if not rg_id:
            raise ValueError('route_group_id is required (direct value or resolvable route_group_name)')
        return rg_id

    def _resolve_person_id(self, api, payload: dict[str, Any]) -> str | None:
        if payload.get('user_id'):
            return payload['user_id']
        email = payload.get('user_email')
        if not email:
            return None
        person = next(api.people.list(email=email), None)
        if person:
            payload['user_id'] = person.person_id
            return person.person_id
        return None

    def _resolve_workspace_id(self, api, payload: dict[str, Any]) -> str | None:
        if payload.get('workspace_id'):
            return payload['workspace_id']
        workspace_name = payload.get('workspace_name')
        if not workspace_name:
            return None
        for ws in api.workspaces.list(display_name=workspace_name):
            if ws.display_name == workspace_name:
                payload['workspace_id'] = ws.workspace_id
                return ws.workspace_id
        return None

    def _legacy_target(self, payload: dict[str, Any]) -> str | None:
        if payload.get('legacy_forward_target'):
            return payload['legacy_forward_target']
        ext = (payload.get('extension') or '').strip()
        if not ext:
            return None
        prefix = (payload.get('legacy_forward_prefix') or '53').strip()
        return f'+{prefix}{ext[1:]}' if ext.startswith('8') else f'+{prefix}{ext}'

    def _outgoing_profile_settings(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        policy, _, _, _ = self._load_all()
        profile = payload.get('outgoing_profile') or payload.get('default_outgoing_profile') or policy.get('default_outgoing_profile')
        outgoing_profiles = policy.get('outgoing_profiles') or {}
        if profile in outgoing_profiles:
            return outgoing_profiles[profile]
        if isinstance(profile, dict):
            return profile
        raise ValueError(f'Outgoing profile not found in static_policy.json: {profile}')

    @staticmethod
    def _split_pipe(raw: str | None) -> list[str]:
        if not raw:
            return []
        return [item.strip() for item in raw.split('|') if item.strip()]

    @staticmethod
    def _safe_model(value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, 'model_dump'):
            return value.model_dump(mode='json', by_alias=True)
        if isinstance(value, list):
            return [V21Runner._safe_model(v) for v in value]
        if isinstance(value, dict):
            return {k: V21Runner._safe_model(v) for k, v in value.items()}
        if hasattr(value, '__dict__'):
            return asdict(value)
        return value

    def _build_plan(self, *, locations, users, workspaces, policy: dict[str, Any]) -> list[PlannedAction]:
        actions: list[PlannedAction] = []

        for location in locations:
            location_key = location.location_id or location.location_name
            outgoing = location.default_outgoing_profile or policy.get('default_outgoing_profile') or 'profile_2'
            base_payload = dict(location.payload)
            base_payload['default_outgoing_profile'] = outgoing
            actions.extend(
                [
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_CREATE_AND_ACTIVATE, 'apply', 'Crear/activar sede y preparar Webex Calling', base_payload),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_ROUTE_GROUP_RESOLVE, 'apply', 'Resolver routeGroupId requerido para PSTN', base_payload),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_PSTN_CONFIGURE, 'apply', 'Configurar PSTN en sede', base_payload),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_NUMBERS_ADD_DISABLED, 'apply', 'Alta de DDI en estado desactivado', base_payload),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_MAIN_DDI_ASSIGN, 'apply', 'Asignar DDI cabecera a la sede', base_payload),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_INTERNAL_CALLING_CONFIG, 'apply', 'Configurar llamadas internas', base_payload),
                    PlannedAction(EntityType.LOCATION, location_key, Stage.LOCATION_OUTGOING_PERMISSION_DEFAULT, 'apply', f'Aplicar perfil saliente por defecto: {outgoing}', base_payload),
                ]
            )

        for user in users:
            user_key = user.user_id or user.user_email
            base_payload = dict(user.payload)
            actions.extend(
                [
                    PlannedAction(EntityType.USER, user_key, Stage.USER_LEGACY_INTERCOM_SECONDARY, 'apply', 'Agregar intercom legacy secundario', base_payload),
                    PlannedAction(EntityType.USER, user_key, Stage.USER_LEGACY_FORWARD_PREFIX_53, 'apply', 'Configurar desvío legacy con prefijo 53', base_payload),
                ]
            )
            if user.outgoing_profile:
                actions.append(
                    PlannedAction(EntityType.USER, user_key, Stage.USER_OUTGOING_PERMISSION_OVERRIDE, 'apply', f'Aplicar perfil saliente no-default: {user.outgoing_profile}', base_payload)
                )

        for workspace in workspaces:
            workspace_key = workspace.workspace_id or workspace.workspace_name
            base_payload = dict(workspace.payload)
            actions.extend(
                [
                    PlannedAction(EntityType.WORKSPACE, workspace_key, Stage.WORKSPACE_LEGACY_INTERCOM_SECONDARY, 'apply', 'Agregar intercom legacy secundario', base_payload),
                    PlannedAction(EntityType.WORKSPACE, workspace_key, Stage.WORKSPACE_LEGACY_FORWARD_PREFIX_53, 'apply', 'Configurar desvío legacy con prefijo 53', base_payload),
                ]
            )
            if workspace.outgoing_profile:
                actions.append(
                    PlannedAction(EntityType.WORKSPACE, workspace_key, Stage.WORKSPACE_OUTGOING_PERMISSION_OVERRIDE, 'apply', f'Aplicar perfil saliente no-default: {workspace.outgoing_profile}', base_payload)
                )

        return actions
