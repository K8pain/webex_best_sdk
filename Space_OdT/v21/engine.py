from __future__ import annotations

import asyncio
import csv
import datetime as dt
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wxc_sdk.as_api import AsLocationsApi, AsWebexSimpleApi

from .io import bootstrap_v21_inputs, load_locations, save_json, write_plan_csv
from .models import EntityType, LocationInput, PlannedAction, RunSummary, Stage


class MissingV21InputsError(RuntimeError):
    """Raised when required v2.1 input templates were generated."""


@dataclass
class LocationBulkJob:
    job_id: str
    created_at: str
    input_path: str
    status: str
    totals: dict[str, int] = field(default_factory=dict)
    cursor: dict[str, int] = field(default_factory=dict)
    entity_type: str = 'location'

    def to_dict(self) -> dict[str, Any]:
        return {
            'job_id': self.job_id,
            'created_at': self.created_at,
            'input_path': self.input_path,
            'status': self.status,
            'totals': self.totals,
            'cursor': self.cursor,
            'entity_type': self.entity_type,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> 'LocationBulkJob':
        return cls(
            job_id=str(payload['job_id']),
            created_at=str(payload['created_at']),
            input_path=str(payload['input_path']),
            status=str(payload.get('status', 'created')),
            totals=dict(payload.get('totals') or {}),
            cursor=dict(payload.get('cursor') or {}),
            entity_type=str(payload.get('entity_type', 'location')),
        )


class V21Runner:
    def __init__(self, *, token: str, out_dir: Path):
        self.token = token
        self.out_dir = out_dir

    @property
    def v21_dir(self) -> Path:
        return self.out_dir / 'v21'

    @property
    def jobs_dir(self) -> Path:
        return self.v21_dir / 'jobs'

    @property
    def verbose_log_path(self) -> Path:
        return self.v21_dir / 'api_verbose.log'

    def _log_verbose(self, *, event: str, method: str, payload: dict[str, Any] | None = None) -> None:
        entry = {
            'ts': dt.datetime.now(dt.timezone.utc).isoformat(),
            'event': event,
            'method': method,
            'payload': payload or {},
        }
        self.verbose_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.verbose_log_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + '\n')

    async def _call_logged(self, method_name: str, awaitable):
        self._log_verbose(event='request', method=method_name)
        try:
            result = await awaitable
            self._log_verbose(event='response', method=method_name, payload={'ok': True})
            return result
        except Exception as exc:  # noqa: BLE001
            self._log_verbose(
                event='response',
                method=method_name,
                payload={'ok': False, 'error_type': type(exc).__name__, 'error': str(exc)},
            )
            raise

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
        locations = load_locations(self.v21_dir / 'input_locations.csv')
        actions = self._build_plan(locations=locations)
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

    def create_location_job(self, *, rows: list[dict[str, Any]], entity_type: str = 'location') -> LocationBulkJob:
        if entity_type != 'location':
            raise ValueError('entity_type no soportado en v21 (usar location)')
        job_id = str(uuid.uuid4())
        created_at = dt.datetime.now(dt.timezone.utc).isoformat()
        job_dir = self.jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        input_path = job_dir / 'input_rows.json'
        input_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

        job = LocationBulkJob(
            job_id=job_id,
            created_at=created_at,
            input_path=str(input_path),
            status='created',
            totals={'total': len(rows), 'processed': 0, 'success': 0, 'pending': 0, 'rejected': 0},
            cursor={'offset': 0},
            entity_type=entity_type,
        )
        self.save_job(job)
        self._write_checkpoint(job)
        return job

    def get_job(self, job_id: str) -> LocationBulkJob:
        payload = json.loads((self.jobs_dir / f'{job_id}.json').read_text(encoding='utf-8'))
        return LocationBulkJob.from_dict(payload)

    def save_job(self, job: LocationBulkJob) -> None:
        save_json(self.jobs_dir / f'{job.job_id}.json', job.to_dict())

    def get_job_result(self, job_id: str) -> dict[str, Any]:
        job_dir = self.jobs_dir / job_id
        final_state = job_dir / 'final_state.json'
        if not final_state.exists():
            raise FileNotFoundError('resultado final aún no disponible')
        return json.loads(final_state.read_text(encoding='utf-8'))

    def get_async_execution_info(self) -> dict[str, Any]:
        """Expose where async API methods are used for operator visibility in UI/API."""
        return {
            'uses_async_api': True,
            'engine_method': 'process_location_job',
            'session_class': 'AsWebexSimpleApi',
            'locations_class': 'AsLocationsApi',
            'awaited_calls': [
                'api.people.me()',
                'locations_api.by_name()',
                'locations_api.create()',
                'locations_api.details()',
                'locations_api.update()',
            ],
        }

    def get_latest_final_state(self) -> dict[str, Any]:
        """Return most recent final state snapshot for pre-upload UI visibility."""
        if not self.jobs_dir.exists():
            return {'items': [], 'source': 'none'}
        candidates: list[tuple[float, Path]] = []
        for path in self.jobs_dir.glob('*/final_state.json'):
            try:
                candidates.append((path.stat().st_mtime, path))
            except OSError:
                continue
        if not candidates:
            legacy = self.v21_dir / 'results_locations.json'
            if legacy.exists():
                data = json.loads(legacy.read_text(encoding='utf-8'))
                return {'items': data.get('items', []), 'source': str(legacy)}
            return {'items': [], 'source': 'none'}

        _, newest = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
        payload = json.loads(newest.read_text(encoding='utf-8'))
        items = payload.get('remote_final_state', {}).get('items', [])
        return {'items': items, 'source': str(newest)}

    async def process_location_job(self, job_id: str, *, chunk_size: int = 200, max_concurrency: int = 20) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job.entity_type != 'location':
            raise ValueError('Solo location está habilitado en v21')
        if job.status == 'running':
            return job.to_dict()

        job.status = 'running'
        self.save_job(job)
        rows_payload = json.loads(Path(job.input_path).read_text(encoding='utf-8'))
        rows = [self._location_input_from_job_row(payload, index + 1) for index, payload in enumerate(rows_payload)]

        job_dir = self.jobs_dir / job_id
        results_csv = job_dir / 'results.csv'
        pending_csv = job_dir / 'pending_rows.csv'
        rejected_csv = job_dir / 'rejected_rows.csv'
        final_state_json = job_dir / 'final_state.json'

        self._init_result_files(results_csv, pending_csv, rejected_csv)
        snapshots: list[dict[str, Any]] = []

        start_offset = int(job.cursor.get('offset', 0))
        async with AsWebexSimpleApi(tokens=self.token, concurrent_requests=max_concurrency) as api:
            locations_api = AsLocationsApi(session=api.session)
            await self._call_logged('api.people.me', api.people.me())

            offset = start_offset
            while offset < len(rows):
                chunk = rows[offset : offset + chunk_size]
                chunk_results = await self._process_chunk(
                    locations_api=locations_api,
                    rows=chunk,
                    max_concurrency=max_concurrency,
                    snapshots=snapshots,
                )
                self._append_results(rows=chunk_results, results_csv=results_csv, pending_csv=pending_csv, rejected_csv=rejected_csv)
                self._update_totals(job, chunk_results)
                offset += len(chunk)
                job.cursor = {'offset': offset}
                self.save_job(job)
                self._write_checkpoint(job)

        summary = {
            'job': job.to_dict(),
            'totals': job.totals,
            'remote_final_state': {'items': snapshots},
        }
        save_json(final_state_json, summary)
        save_json(self.v21_dir / 'results_locations.json', {'items': snapshots})
        job.status = 'completed'
        self.save_job(job)
        self._write_checkpoint(job)
        summary['job'] = job.to_dict()
        return summary

    async def _process_chunk(
        self,
        *,
        locations_api: AsLocationsApi,
        rows: list[LocationInput],
        max_concurrency: int,
        snapshots: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        sem = asyncio.Semaphore(max_concurrency)

        async def worker(row: LocationInput) -> dict[str, Any]:
            async with sem:
                result = await self._upsert_location(locations_api, row, apply=True)
                if result.get('remote_id'):
                    details = await self._safe_fetch_details(locations_api, result['remote_id'], row)
                    if details is not None:
                        snapshots.append(self._to_jsonable_location(details))
                return result

        return await asyncio.gather(*(worker(row) for row in rows), return_exceptions=False)

    async def _safe_fetch_details(self, locations_api: AsLocationsApi, remote_id: str, row: LocationInput) -> Any | None:
        try:
            return await self._call_logged(
                'locations_api.details',
                locations_api.details(remote_id, org_id=row.org_id),
            )
        except Exception:
            try:
                return await self._call_logged(
                    'locations_api.by_name',
                    locations_api.by_name(row.location_name, org_id=row.org_id),
                )
            except Exception:
                return None

    def _update_totals(self, job: LocationBulkJob, results: list[dict[str, Any]]) -> None:
        job.totals['processed'] = int(job.totals.get('processed', 0)) + len(results)
        job.totals['success'] = int(job.totals.get('success', 0)) + sum(1 for item in results if item['status'] == 'success')
        job.totals['pending'] = int(job.totals.get('pending', 0)) + sum(1 for item in results if item['status'] == 'pending')
        job.totals['rejected'] = int(job.totals.get('rejected', 0)) + sum(1 for item in results if item['status'] == 'rejected')

    def _write_checkpoint(self, job: LocationBulkJob) -> None:
        save_json(self.jobs_dir / job.job_id / 'checkpoint.json', {'job': job.to_dict()})

    def _init_result_files(self, results_csv: Path, pending_csv: Path, rejected_csv: Path) -> None:
        headers = ['row_number', 'location_key', 'status', 'remote_id', 'error_classification', 'error_type', 'error']
        for path in (results_csv, pending_csv, rejected_csv):
            if path.exists():
                continue
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=headers)
                writer.writeheader()

    def _append_results(self, *, rows: list[dict[str, Any]], results_csv: Path, pending_csv: Path, rejected_csv: Path) -> None:
        self._append_csv(results_csv, rows)
        pending = [row for row in rows if row['status'] == 'pending']
        rejected = [row for row in rows if row['status'] == 'rejected']
        if pending:
            self._append_csv(pending_csv, pending)
        if rejected:
            self._append_csv(rejected_csv, rejected)

    def _append_csv(self, path: Path, rows: list[dict[str, Any]]) -> None:
        headers = ['row_number', 'location_key', 'status', 'remote_id', 'error_classification', 'error_type', 'error']
        with path.open('a', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writerows(rows)

    @staticmethod
    def _location_input_from_job_row(row: dict[str, Any], row_number: int) -> LocationInput:
        payload = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        location_name = str(payload.get('location_name') or payload.get('name') or '').strip()
        if not location_name:
            raise ValueError(f'row {row_number}: location_name/name is required')
        payload.setdefault('name', location_name)
        payload.setdefault('location_name', location_name)
        return LocationInput(
            row_number=row_number,
            location_name=location_name,
            location_id=str(payload.get('location_id') or '').strip() or None,
            org_id=str(payload.get('org_id') or '').strip() or None,
            route_group_id=str(payload.get('route_group_id') or '').strip() or None,
            main_number=str(payload.get('main_number') or '').strip() or None,
            default_outgoing_profile=str(payload.get('default_outgoing_profile') or '').strip() or None,
            payload=payload,
        )

    async def run_locations_async(self, rows: list[LocationInput], *, apply: bool = True, max_concurrency: int = 20) -> dict[str, Any]:
        # compat entrypoint, now writes to the same unified artifacts
        raw_rows = [row.payload for row in rows]
        job = self.create_location_job(rows=raw_rows, entity_type='location')
        if not apply:
            job.status = 'completed'
            job.totals['pending'] = len(rows)
            job.totals['processed'] = len(rows)
            self.save_job(job)
            self._write_checkpoint(job)
            return {'summary': job.totals, 'items': [], 'snapshot': {'items': []}}
        result = await self.process_location_job(job.job_id, max_concurrency=max_concurrency)
        return {
            'summary': result['totals'],
            'items': [],
            'snapshot': result['remote_final_state'],
        }

    async def _upsert_location(self, locations_api: AsLocationsApi, row: LocationInput, *, apply: bool) -> dict[str, Any]:
        location_key = self._stable_location_key(row)
        try:
            existing = await self._call_logged(
                'locations_api.by_name',
                locations_api.by_name(row.location_name, org_id=row.org_id),
            )
            if not apply:
                return {
                    'row_number': row.row_number,
                    'location_key': location_key,
                    'status': 'pending',
                    'remote_id': existing.location_id if existing else None,
                    'error_classification': None,
                    'error_type': None,
                    'error': None,
                }

            remote_id: str | None = None
            if existing is None:
                self._validate_required_fields(row)
                remote_id = await self._call_logged(
                    'locations_api.create',
                    locations_api.create(
                        name=row.location_name,
                        time_zone=row.payload.get('time_zone') or '',
                        preferred_language=row.payload.get('preferred_language') or '',
                        announcement_language=row.payload.get('announcement_language') or '',
                        address1=row.payload.get('address1') or '',
                        address2=row.payload.get('address2') or None,
                        city=row.payload.get('city') or '',
                        state=row.payload.get('state') or '',
                        postal_code=row.payload.get('postal_code') or '',
                        country=row.payload.get('country') or '',
                        org_id=row.org_id,
                    ),
                )
            else:
                settings = await self._call_logged(
                    'locations_api.details',
                    locations_api.details(existing.location_id, org_id=row.org_id),
                )
                if row.payload.get('time_zone'):
                    settings.time_zone = row.payload.get('time_zone')
                if row.payload.get('preferred_language'):
                    settings.preferred_language = row.payload.get('preferred_language')
                if row.payload.get('announcement_language'):
                    settings.announcement_language = row.payload.get('announcement_language')
                if settings.address is not None:
                    if row.payload.get('address1'):
                        settings.address.address1 = row.payload.get('address1')
                    if row.payload.get('address2'):
                        settings.address.address2 = row.payload.get('address2')
                    if row.payload.get('city'):
                        settings.address.city = row.payload.get('city')
                    if row.payload.get('state'):
                        settings.address.state = row.payload.get('state')
                    if row.payload.get('postal_code'):
                        settings.address.postal_code = row.payload.get('postal_code')
                    if row.payload.get('country'):
                        settings.address.country = row.payload.get('country')
                await self._call_logged(
                    'locations_api.update',
                    locations_api.update(existing.location_id, settings=settings, org_id=row.org_id),
                )
                remote_id = existing.location_id

            return {
                'row_number': row.row_number,
                'location_key': location_key,
                'status': 'success',
                'remote_id': remote_id,
                'error_classification': None,
                'error_type': None,
                'error': None,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                'row_number': row.row_number,
                'location_key': location_key,
                'status': 'rejected',
                'remote_id': None,
                'error_classification': self._classify_error(exc),
                'error_type': type(exc).__name__,
                'error': str(exc),
            }

    @staticmethod
    def _stable_location_key(row: LocationInput) -> str:
        external_id = row.payload.get('location_external_id') or row.payload.get('external_id')
        if external_id:
            return str(external_id)
        return row.location_name

    @staticmethod
    def _classify_error(exc: Exception) -> str:
        message = str(exc).lower()
        retryable_markers = ('timeout', 'tempor', '429', 'too many', 'connection', 'unavailable')
        if any(marker in message for marker in retryable_markers):
            return 'retryable'
        return 'non_retryable'

    @staticmethod
    def _to_jsonable_location(location: Any) -> dict[str, Any]:
        if hasattr(location, 'model_dump'):
            return location.model_dump(mode='json', by_alias=True, exclude_none=True)
        return dict(location)

    @staticmethod
    def _validate_required_fields(row: LocationInput) -> None:
        required = ('time_zone', 'preferred_language', 'announcement_language', 'address1', 'city', 'state', 'postal_code', 'country')
        missing = [field for field in required if not (row.payload.get(field) or '').strip()]
        if missing:
            raise ValueError(f"row {row.row_number}: missing required fields for create: {', '.join(missing)}")

    def _build_plan(self, *, locations: list[LocationInput]) -> list[PlannedAction]:
        actions: list[PlannedAction] = []
        for location in locations:
            location_key = location.location_id or location.location_name
            actions.append(
                PlannedAction(
                    EntityType.LOCATION,
                    location_key,
                    Stage.LOCATION_CREATE_AND_ACTIVATE,
                    'manual_closure',
                    'Alta/actualización determinista de sede',
                )
            )
        return actions
