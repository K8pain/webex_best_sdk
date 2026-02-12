import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from Space_OdT import sdk_client


class DummyApi:
    def __init__(self, tokens: str):
        self.tokens = tokens


def test_create_api_reads_token_from_parent_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_dir = tmp_path / 'repo'
    nested_dir = project_dir / 'Space_OdT' / 'run'
    nested_dir.mkdir(parents=True)
    (project_dir / '.env').write_text('WEBEX_ACCESS_TOKEN=abc123\n')

    monkeypatch.chdir(nested_dir)
    monkeypatch.delenv('WEBEX_ACCESS_TOKEN', raising=False)
    monkeypatch.setitem(sys.modules, 'wxc_sdk', SimpleNamespace(WebexSimpleApi=DummyApi))

    api = sdk_client.create_api()

    assert isinstance(api, DummyApi)
    assert api.tokens == 'abc123'


def test_create_api_uses_existing_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('WEBEX_ACCESS_TOKEN', 'from_env')
    monkeypatch.setitem(sys.modules, 'wxc_sdk', SimpleNamespace(WebexSimpleApi=DummyApi))

    api = sdk_client.create_api()

    assert api.tokens == 'from_env'


def test_create_api_prefers_dotenv_over_existing_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_dir = tmp_path / 'repo'
    nested_dir = project_dir / 'Space_OdT' / 'run'
    nested_dir.mkdir(parents=True)
    (project_dir / '.env').write_text('WEBEX_ACCESS_TOKEN=from_dotenv\n')

    monkeypatch.chdir(nested_dir)
    monkeypatch.setenv('WEBEX_ACCESS_TOKEN', 'from_env')
    monkeypatch.setitem(sys.modules, 'wxc_sdk', SimpleNamespace(WebexSimpleApi=DummyApi))

    api = sdk_client.create_api()

    assert api.tokens == 'from_dotenv'


def test_create_api_prefers_explicit_token_over_env_and_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_dir = tmp_path / 'repo'
    nested_dir = project_dir / 'Space_OdT' / 'run'
    nested_dir.mkdir(parents=True)
    (project_dir / '.env').write_text('WEBEX_ACCESS_TOKEN=from_dotenv\n')

    monkeypatch.chdir(nested_dir)
    monkeypatch.setenv('WEBEX_ACCESS_TOKEN', 'from_env')
    monkeypatch.setitem(sys.modules, 'wxc_sdk', SimpleNamespace(WebexSimpleApi=DummyApi))

    api = sdk_client.create_api(token='from_arg')

    assert api.tokens == 'from_arg'


def test_create_api_raises_without_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('WEBEX_ACCESS_TOKEN', raising=False)
    monkeypatch.setitem(sys.modules, 'wxc_sdk', SimpleNamespace(WebexSimpleApi=DummyApi))

    with pytest.raises(sdk_client.MissingTokenError):
        sdk_client.create_api()
