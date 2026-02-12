from __future__ import annotations

import asyncio
import datetime as dt
import json
import uuid
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Callable

from wxc_sdk.as_api import AsWebexSimpleApi
from wxc_sdk.har_writer import HarWriter
from wxc_sdk.licenses import LicenseProperties, LicenseRequest
from wxc_sdk.person_settings.call_intercept import InterceptSetting
from wxc_sdk.person_settings.forwarding import PersonForwardingSetting
from wxc_sdk.person_settings.numbers import UpdatePersonNumbers
from wxc_sdk.person_settings.permissions_in import IncomingPermissions
from wxc_sdk.person_settings.permissions_out import OutgoingPermissions
from wxc_sdk.person_settings.voicemail import VoicemailSettings
from wxc_sdk.telephony.callqueue.agents import AgentCallQueueSetting

from .io import (
    append_failures,
    load_input_records,
    load_policy,
    load_run_state,
    load_stage_overrides,
    load_v1_maps,
    save_run_state,
    write_change_log,
    write_html_report,
)
from .models import ChangeEntry, FailureEntry, InputRecord, RecordResult, Stage, StageDecision

DecisionProvider = Callable[[Stage], tuple[StageDecision, str | None]]


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json', by_alias=True)
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    return value


def parse_stage_decision(raw: str) -> tuple[StageDecision, str | None]:
    clean = raw.strip()
    if not clean:
        raise ValueError('empty decision')
    parts = clean.split(maxsplit=1)
    cmd = parts[0].lower()
    if cmd == 'yes':
        return StageDecision.YES, None
    if cmd == 'no':
        return StageDecision.NO, None
    if cmd == 'yesbut':
        if len(parts) == 1:
            raise ValueError('yesbut requiere ruta de archivo')
        return StageDecision.YESBUT, parts[1].strip()
    raise ValueError("decision inválida, use yes|no|yesbut <archivo>")


class V2Runner:
    def __init__(
        self,
        *,
        token: str,
        out_dir: Path,
        concurrent_requests: int = 10,
        debug_har: bool = False,
        decision_provider: DecisionProvider | None = None,
    ):
        self.token = token
        self.out_dir = out_dir
        self.concurrent_requests = concurrent_requests
        self.debug_har = debug_har
        self.decision_provider = decision_provider

    async def run(self, *, only_failures: bool = False) -> dict[str, Any]:
        v2_dir = self.out_dir / 'v2'
        v2_dir.mkdir(parents=True, exist_ok=True)
        policy = load_policy(v2_dir / 'static_policy.json')
        records = load_input_records(v2_dir / 'input_softphones.csv')
        resolvers = load_v1_maps(self.out_dir / 'v1_inventory')

        state_path = v2_dir / 'run_state.json'
        failures_path = v2_dir / 'failures.csv'
        state = load_run_state(state_path)
        run_id = str(uuid.uuid4())
        state.update({'run_id': run_id, 'started_at': dt.datetime.now(dt.timezone.utc).isoformat()})

        stage_decisions, stage_overrides = self._collect_stage_decisions(v2_dir)
        state['stage_decisions'] = {
            s.value: {'decision': d.value, 'override_path': p} for s, (d, p) in stage_decisions.items()
        }

        pending_records = self._build_pending(records, state, only_failures=only_failures)
        sem = asyncio.Semaphore(self.concurrent_requests)
        har = HarWriter(file_name=str(v2_dir / 'http.har')) if self.debug_har else None

        failures: list[FailureEntry] = []
        changes: list[ChangeEntry] = []

        async with AsWebexSimpleApi(tokens=self.token, concurrent_requests=self.concurrent_requests) as api:
            if har:
                api.session.har_writer = har
            await api.people.me()
            await api.licenses.list()

            async def worker(record: InputRecord) -> None:
                async with sem:
                    result, row_failures, row_changes = await self._process_record(
                        api,
                        record,
                        resolvers,
                        policy,
                        stage_decisions,
                        stage_overrides,
                    )
                    state['record_results'][record.user_email] = asdict(result)
                    failures.extend(row_failures)
                    changes.extend(row_changes)

            await asyncio.gather(*(worker(record) for record in pending_records))

        state['completed_count'] = sum(1 for r in state['record_results'].values() if r.get('status') == 'success')
        state['failed_count'] = sum(1 for r in state['record_results'].values() if r.get('status') == 'failed')

        save_run_state(state_path, state)
        if failures:
            append_failures(failures_path, failures)
        write_change_log(v2_dir / 'changes.log', changes)
        write_html_report(v2_dir / 'report.html', run_id=run_id, changes=changes, failures=failures)
        return state

    def _collect_stage_decisions(self, v2_dir: Path) -> tuple[dict[Stage, tuple[StageDecision, str | None]], dict[Stage, dict[str, dict[str, Any]]]]:
        decisions: dict[Stage, tuple[StageDecision, str | None]] = {}
        overrides: dict[Stage, dict[str, dict[str, Any]]] = {}
        for stage in Stage:
            decision, path = self._ask_decision(stage)
            decisions[stage] = (decision, path)
            if decision == StageDecision.YESBUT and path:
                overrides[stage] = load_stage_overrides((v2_dir / path) if not Path(path).is_absolute() else Path(path))
        return decisions, overrides

    def _ask_decision(self, stage: Stage) -> tuple[StageDecision, str | None]:
        if self.decision_provider is not None:
            return self.decision_provider(stage)
        while True:
            raw = input(f"Aplicar {stage.value}? [yes/no/yesbut <archivo>] ").strip()
            try:
                return parse_stage_decision(raw)
            except ValueError as exc:
                print(str(exc))

    @staticmethod
    def _build_pending(records: list[InputRecord], state: dict[str, Any], *, only_failures: bool) -> list[InputRecord]:
        if not only_failures:
            return records
        previous = state.get('record_results', {})
        return [record for record in records if previous.get(record.user_email, {}).get('status') == 'failed']

    async def _process_record(
        self,
        api: AsWebexSimpleApi,
        record: InputRecord,
        resolvers: dict[str, dict[str, str]],
        policy: dict[str, Any],
        stage_decisions: dict[Stage, tuple[StageDecision, str | None]],
        stage_overrides: dict[Stage, dict[str, dict[str, Any]]],
    ) -> tuple[RecordResult, list[FailureEntry], list[ChangeEntry]]:
        failures: list[FailureEntry] = []
        changes: list[ChangeEntry] = []

        person_id = resolvers['email_to_person_id'].get(record.user_email)
        if not person_id:
            failure = FailureEntry(record.user_email, 'resolve_person', 'ValidationError', None, None, 'Person not found in V1 inventory map')
            return RecordResult(user_email=record.user_email, status='failed', failed_stage='resolve_person'), [failure], changes

        location_id = record.location_id
        if not location_id.startswith('Y2lzY29zcGFyazovL3VzL0xPQ0FUSU9OLw'):
            location_id = resolvers['location_name_to_id'].get(record.location_id.lower(), record.location_id)

        stages = self._build_stages(record)
        executed: list[str] = []
        for stage in stages:
            decision, _ = stage_decisions[stage]
            if decision == StageDecision.NO:
                changes.append(ChangeEntry(record.user_email, stage.value, 'skipped', None, None, 'skipped_by_operator'))
                continue

            override_payload = stage_overrides.get(stage, {}).get(record.user_email, {}) if decision == StageDecision.YESBUT else {}
            stage_record = replace(record, payload={**record.payload, **override_payload})
            before = await self._read_stage_state(api, stage, person_id)
            try:
                await self._apply_stage(api, stage, stage_record, person_id, location_id, policy, resolvers)
                after = await self._read_stage_state(api, stage, person_id)
                changes.append(ChangeEntry(record.user_email, stage.value, 'success', before, after, 'applied'))
                executed.append(stage.value)
            except Exception as exc:
                after = await self._read_stage_state(api, stage, person_id)
                changes.append(ChangeEntry(record.user_email, stage.value, 'failed', before, after, str(exc)))
                failures.append(
                    FailureEntry(
                        user_email=record.user_email,
                        stage=stage.value,
                        error_type=type(exc).__name__,
                        http_status=getattr(exc, 'status_code', None),
                        tracking_id=getattr(exc, 'tracking_id', None),
                        details=str(exc),
                    )
                )
                return RecordResult(user_email=record.user_email, status='failed', failed_stage=stage.value), failures, changes

        await api.people.details(person_id=person_id, calling_data=True)
        return RecordResult(user_email=record.user_email, status='success', verified=True, details={'stages': executed}), failures, changes

    @staticmethod
    def _build_stages(record: InputRecord) -> list[Stage]:
        stages = [Stage.ASSIGN_CALLING_LICENSE]
        if record.payload.get('alternate_numbers'):
            stages.append(Stage.APPLY_NUMBERS_UPDATE)
        if any(record.payload.get(k) is not None for k in ('cf_always_enabled', 'cf_busy_enabled', 'cf_noanswer_enabled')):
            stages.append(Stage.APPLY_FORWARDING)
        if record.payload.get('voicemail_enabled') is not None:
            stages.append(Stage.APPLY_VOICEMAIL)
        if record.payload.get('intercept_enabled') is not None:
            stages.append(Stage.APPLY_CALL_INTERCEPT)
        if record.payload.get('incoming_permissions_mode') or record.payload.get('outgoing_permissions_mode'):
            stages.append(Stage.APPLY_PERMISSIONS)
        if record.payload.get('call_queue_ids') or record.payload.get('call_queue_names'):
            stages.append(Stage.APPLY_CALL_QUEUE_MEMBERSHIPS)
        return stages

    async def _read_stage_state(self, api: AsWebexSimpleApi, stage: Stage, person_id: str) -> Any:
        if stage == Stage.ASSIGN_CALLING_LICENSE:
            return _to_jsonable(await api.people.details(person_id=person_id, calling_data=True))
        if stage == Stage.APPLY_NUMBERS_UPDATE:
            return _to_jsonable(await api.person_settings.numbers.read(person_id=person_id))
        if stage == Stage.APPLY_FORWARDING:
            return _to_jsonable(await api.person_settings.forwarding.read(entity_id=person_id))
        if stage == Stage.APPLY_VOICEMAIL:
            return _to_jsonable(await api.person_settings.voicemail.read(entity_id=person_id))
        if stage == Stage.APPLY_CALL_INTERCEPT:
            return _to_jsonable(await api.person_settings.call_intercept.read(entity_id=person_id))
        if stage == Stage.APPLY_PERMISSIONS:
            return {
                'incoming': _to_jsonable(await api.person_settings.permissions_in.read(entity_id=person_id)),
                'outgoing': _to_jsonable(await api.person_settings.permissions_out.read(entity_id=person_id)),
            }
        if stage == Stage.APPLY_CALL_QUEUE_MEMBERSHIPS:
            return _to_jsonable(await api.telephony.callqueue.agents.details(id=person_id))
        return None

    async def _apply_stage(
        self,
        api: AsWebexSimpleApi,
        stage: Stage,
        record: InputRecord,
        person_id: str,
        location_id: str,
        policy: dict[str, Any],
        resolvers: dict[str, dict[str, str]],
    ) -> None:
        if stage == Stage.ASSIGN_CALLING_LICENSE:
            req = LicenseRequest(
                id=record.calling_license_id,
                properties=LicenseProperties(location_id=location_id, extension=record.extension, phone_number=record.phone_number),
            )
            await api.licenses.assign_licenses_to_users(person_id=person_id, licenses=[req])
            return

        if stage == Stage.APPLY_NUMBERS_UPDATE:
            update = UpdatePersonNumbers.model_validate(json.loads(record.payload['alternate_numbers']))
            await api.person_settings.numbers.update(person_id=person_id, update=update)
            return

        if stage == Stage.APPLY_FORWARDING:
            merged = dict(policy.get('forwarding_defaults') or {})
            merged.update({k: v for k, v in record.payload.items() if k.startswith('cf_') and v is not None})
            await api.person_settings.forwarding.configure(
                entity_id=person_id,
                forwarding=PersonForwardingSetting.model_validate(merged),
            )
            return

        if stage == Stage.APPLY_VOICEMAIL:
            merged = dict(policy.get('voicemail_defaults') or {})
            merged.update({k: v for k, v in record.payload.items() if k.startswith('voicemail_') and v is not None})
            await api.person_settings.voicemail.configure(entity_id=person_id, settings=VoicemailSettings.model_validate(merged))
            return

        if stage == Stage.APPLY_CALL_INTERCEPT:
            merged = dict(policy.get('intercept_defaults') or {})
            merged.update({k: v for k, v in record.payload.items() if k.startswith('intercept_') and v is not None})
            await api.person_settings.call_intercept.configure(entity_id=person_id, intercept=InterceptSetting.model_validate(merged))
            return

        if stage == Stage.APPLY_PERMISSIONS:
            in_payload = json.loads(record.payload['incoming_permissions_json']) if record.payload.get('incoming_permissions_json') else (policy.get('incoming_permissions_defaults') or {})
            out_payload = json.loads(record.payload['outgoing_permissions_json']) if record.payload.get('outgoing_permissions_json') else (policy.get('outgoing_permissions_defaults') or {})
            await api.person_settings.permissions_in.configure(entity_id=person_id, settings=IncomingPermissions.model_validate(in_payload))
            await api.person_settings.permissions_out.configure(entity_id=person_id, settings=OutgoingPermissions.model_validate(out_payload))
            return

        if stage == Stage.APPLY_CALL_QUEUE_MEMBERSHIPS:
            queue_ids = [q.strip() for q in (record.payload.get('call_queue_ids') or '').split('|') if q.strip()]
            if not queue_ids:
                names = [q.strip().lower() for q in (record.payload.get('call_queue_names') or '').split('|') if q.strip()]
                queue_ids = [resolvers['queue_name_to_id'][name] for name in names if name in resolvers['queue_name_to_id']]
            join_enabled = bool(record.payload.get('join_enabled', True))
            settings = [AgentCallQueueSetting(queue_id=q, join_enabled=join_enabled) for q in queue_ids]
            await api.telephony.callqueue.agents.update_call_queue_settings(id=person_id, settings=settings)
            return

        raise ValueError(f'Unsupported stage: {stage}')
