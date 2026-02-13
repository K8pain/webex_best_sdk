import sys
from types import SimpleNamespace

import pytest

from Space_OdT import sdk_client


class DummyApi:
    def __init__(self, tokens: str):
        self.tokens = tokens


def test_create_api_uses_existing_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('WEBEX_ACCESS_TOKEN', 'from_env')
    monkeypatch.setitem(sys.modules, 'wxc_sdk', SimpleNamespace(WebexSimpleApi=DummyApi))

    api = sdk_client.create_api()

    assert api.tokens == 'from_env'


def test_create_api_prefers_explicit_token_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('WEBEX_ACCESS_TOKEN', 'from_env')
    monkeypatch.setitem(sys.modules, 'wxc_sdk', SimpleNamespace(WebexSimpleApi=DummyApi))

    api = sdk_client.create_api(token='from_arg')

    assert api.tokens == 'from_arg'


def test_create_api_raises_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('WEBEX_ACCESS_TOKEN', raising=False)
    monkeypatch.setitem(sys.modules, 'wxc_sdk', SimpleNamespace(WebexSimpleApi=DummyApi))

    with pytest.raises(sdk_client.MissingTokenError):
        sdk_client.create_api()


def test_resolve_access_token_trims_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('WEBEX_ACCESS_TOKEN', '  from_env  ')

    token = sdk_client.resolve_access_token()

    assert token == 'from_env'
