from __future__ import annotations

import json
from pathlib import Path

from Space_OdT.v21.engine import LocationBulkJob, V21Runner
from Space_OdT.v21.ui import _run_job_background


def test_create_location_job_persists_minimum_contract(tmp_path: Path):
    runner = V21Runner(token='token', out_dir=tmp_path)
    rows = [
        {
            'location_name': 'Madrid HQ',
            'time_zone': 'Europe/Madrid',
            'preferred_language': 'es_ES',
            'announcement_language': 'es_ES',
            'address1': 'Gran Via 1',
            'city': 'Madrid',
            'state': 'Madrid',
            'postal_code': '28013',
            'country': 'ES',
        }
    ]

    job = runner.create_location_job(rows=rows)

    job_file = tmp_path / 'v21' / 'jobs' / f'{job.job_id}.json'
    checkpoint_file = tmp_path / 'v21' / 'jobs' / job.job_id / 'checkpoint.json'
    assert job_file.exists()
    assert checkpoint_file.exists()

    payload = json.loads(job_file.read_text(encoding='utf-8'))
    hydrated = LocationBulkJob.from_dict(payload)
    assert hydrated.job_id == job.job_id
    assert hydrated.status == 'created'
    assert hydrated.cursor == {'offset': 0}
    assert hydrated.totals['total'] == 1


def test_location_key_prefers_external_id():
    runner = V21Runner(token='token', out_dir=Path('/tmp'))
    row = runner._location_input_from_job_row(
        {
            'location_name': 'Barcelona',
            'external_id': 'loc-123',
        },
        row_number=1,
    )
    assert runner._stable_location_key(row) == 'loc-123'


def test_run_job_background_marks_failed_on_exception(monkeypatch, tmp_path: Path):
    runner = V21Runner(token='token', out_dir=tmp_path)
    job = runner.create_location_job(rows=[{'location_name': 'Bilbao'}])

    async def boom(*args, **kwargs):
        raise RuntimeError('network down')

    monkeypatch.setattr(runner, 'process_location_job', boom)
    _run_job_background(runner, job.job_id)

    failed_job = runner.get_job(job.job_id)
    assert failed_job.status == 'failed'


def test_async_info_and_latest_state_contract(tmp_path: Path):
    runner = V21Runner(token='token', out_dir=tmp_path)
    info = runner.get_async_execution_info()
    assert info['uses_async_api'] is True
    assert 'locations_api.create()' in info['awaited_calls']

    job = runner.create_location_job(rows=[{'location_name': 'Sevilla'}])
    state = {
        'job': job.to_dict(),
        'totals': {'total': 1, 'processed': 1, 'success': 1, 'pending': 0, 'rejected': 0},
        'remote_final_state': {'items': [{'id': 'abc', 'name': 'Sevilla'}]},
    }
    (tmp_path / 'v21' / 'jobs' / job.job_id / 'final_state.json').write_text(json.dumps(state), encoding='utf-8')
    latest = runner.get_latest_final_state()
    assert latest['items'] == [{'id': 'abc', 'name': 'Sevilla'}]


def test_v21_verbose_log_writer_creates_jsonl(tmp_path: Path):
    runner = V21Runner(token='token', out_dir=tmp_path)

    runner._log_verbose(event='request', method='api.people.me')

    log_path = tmp_path / 'v21' / 'api_verbose.log'
    assert log_path.exists()
    content = log_path.read_text(encoding='utf-8')
    assert '"event": "request"' in content
    assert '"method": "api.people.me"' in content


def test_create_location_job_supports_wbxc_entity(tmp_path: Path):
    runner = V21Runner(token='token', out_dir=tmp_path)
    job = runner.create_location_job(rows=[{'location_name': 'Valencia'}], entity_type='location_webex_calling')
    assert job.entity_type == 'location_webex_calling'


def test_html_contains_sidebar_and_wbxc_menu():
    from Space_OdT.v21.ui import _html_page

    html = _html_page()
    assert 'Crear y activar ubicación Webex Calling' in html
    assert '/api/location-wbxc-jobs' in html


def test_list_location_ids_returns_ids_and_metadata(monkeypatch, tmp_path: Path):
    import Space_OdT.v21.engine as engine_mod

    class DummyApi:
        def __init__(self, **kwargs):
            self.session = object()

    class DummyLocation:
        def __init__(self, id: str, name: str):
            self.id = id
            self.name = name
            self.time_zone = 'Europe/Madrid'
            self.preferred_language = 'es_ES'

        def model_dump(self, mode='json', by_alias=True, exclude_none=True):
            return {
                'id': self.id,
                'name': self.name,
                'timeZone': self.time_zone,
                'preferredLanguage': self.preferred_language,
            }

    class DummyLocationsApi:
        def __init__(self, session):
            self.session = session

        def list(self, org_id: str):
            return [DummyLocation('loc-1', 'Madrid HQ'), DummyLocation('loc-2', 'Barcelona')]

    monkeypatch.setattr(engine_mod, 'WebexSimpleApi', DummyApi)
    monkeypatch.setattr(engine_mod, 'LocationsApi', DummyLocationsApi)

    runner = V21Runner(token='token', out_dir=tmp_path)
    payload = __import__('asyncio').run(runner.list_location_ids(org_id='ORG123'))

    assert payload['orgId'] == 'ORG123'
    assert payload['count'] == 2
    assert payload['items'][0]['locationId'] == 'loc-1'


def test_list_location_ids_requires_org_id(tmp_path: Path):
    runner = V21Runner(token='token', out_dir=tmp_path)
    try:
        __import__('asyncio').run(runner.list_location_ids(org_id=''))
    except ValueError as exc:
        assert 'orgId es obligatorio' in str(exc)
    else:
        raise AssertionError('expected ValueError')
