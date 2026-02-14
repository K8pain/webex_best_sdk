from __future__ import annotations

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
