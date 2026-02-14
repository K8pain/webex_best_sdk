from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from Space_OdT.v21.transformacion import launcher_csv_dependencias as launcher


class _ThrottledError(Exception):
    def __init__(self, retry_after: str):
        super().__init__('too many requests')
        self.response = SimpleNamespace(status_code=429, headers={'Retry-After': retry_after})


def test_retry_after_wait_seconds_accepts_numeric():
    assert launcher._retry_after_wait_seconds('5') == 5.0


def test_invoke_with_retry_after_retries_once(monkeypatch):
    sleep_calls: list[float] = []
    monkeypatch.setattr(launcher.time, 'sleep', lambda seconds: sleep_calls.append(seconds))

    calls = {'count': 0}

    def handler(*, token: str, **params):
        calls['count'] += 1
        if calls['count'] == 1:
            raise _ThrottledError('2')
        return {'status': 'ok', 'token': token, 'params': params}

    result = launcher._invoke_with_retry_after(handler=handler, token='tkn', params={'a': 1})

    assert result['status'] == 'ok'
    assert calls['count'] == 2
    assert sleep_calls == [2.0]


def test_invoke_with_retry_after_does_not_retry_without_header(monkeypatch):
    monkeypatch.setattr(launcher.time, 'sleep', lambda _: None)

    class _NoHeaderError(Exception):
        def __init__(self):
            self.response = SimpleNamespace(status_code=429, headers={})

    def handler(*, token: str, **params):
        raise _NoHeaderError()

    with pytest.raises(_NoHeaderError):
        launcher._invoke_with_retry_after(handler=handler, token='tkn', params={})


def test_read_parameter_map_from_parametro_valor_csv(tmp_path):
    csv_path = tmp_path / 'params.csv'
    csv_path.write_text('parametro,valor\nlocation_id,loc-1\nadd_license_ids,"[""lic-a""]"\n', encoding='utf-8')

    parameter_map = launcher._read_parameter_map(csv_path)

    assert parameter_map['location_id'] == 'loc-1'
    assert parameter_map['add_license_ids'] == ['lic-a']


def test_run_script_skips_when_required_dependency_is_missing():
    result = launcher._run_script(
        script_name='ubicacion_actualizar_cabecera',
        parameter_map={'location_id': 'loc1', 'phone_number': ''},
        token='tkn',
        auto_confirm=True,
        dry_run=False,
    )

    assert result['status'] == 'skipped'
    assert result['reason'] == 'missing_dependencies'
    assert result['missing_dependencies'] == 'phone_number'


def test_run_script_parses_and_uses_supported_params(monkeypatch):
    def _fake_handler(token, person_id, add_license_ids, org_id=None):
        return {'status': 'ok', 'kwargs': {'person_id': person_id, 'add_license_ids': add_license_ids, 'org_id': org_id}}

    monkeypatch.setitem(launcher.HANDLERS, 'usuarios_modificar_licencias', _fake_handler)

    result = launcher._run_script(
        script_name='usuarios_modificar_licencias',
        parameter_map={
            'person_id': 'person-1',
            'add_license_ids': ['lic-a'],
            'org_id': 'org-1',
            'remove_license_ids': [],
            'active': True,
        },
        token='tkn',
        auto_confirm=True,
        dry_run=True,
    )

    assert result['status'] == 'dry_run'
    assert result['params']['add_license_ids'] == ['lic-a']
    assert 'active' not in result['params']
