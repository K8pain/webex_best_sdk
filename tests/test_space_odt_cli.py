import importlib
import sys
from types import ModuleType, SimpleNamespace


def _import_cli_with_stubs():
    fake_config = ModuleType('Space_OdT.config')

    class Settings:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    fake_config.Settings = Settings

    fake_export_runner = ModuleType('Space_OdT.export_runner')
    fake_export_runner.run_exports = lambda **kwargs: {
        'exports_dir': '.artifacts/exports',
        'report_path': None,
        'module_counts': {'people': 0},
    }

    fake_sdk_client = ModuleType('Space_OdT.sdk_client')

    class MissingTokenError(RuntimeError):
        pass

    def create_api(*, token=None):
        class DummyApi:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return DummyApi()

    fake_sdk_client.MissingTokenError = MissingTokenError
    fake_sdk_client.create_api = create_api

    sys.modules['Space_OdT.config'] = fake_config
    sys.modules['Space_OdT.export_runner'] = fake_export_runner
    sys.modules['Space_OdT.sdk_client'] = fake_sdk_client

    sys.modules.pop('Space_OdT.cli', None)
    return importlib.import_module('Space_OdT.cli')


def test_parser_accepts_token_option() -> None:
    cli = _import_cli_with_stubs()
    parser = cli.build_parser()
    args = parser.parse_args(['inventory_run', '--token', 'abc123'])

    assert args.command == 'inventory_run'
    assert args.token == 'abc123'


def test_inventory_run_passes_token_to_create_api(monkeypatch) -> None:
    cli = _import_cli_with_stubs()
    captured = {}

    def fake_create_api(*, token=None):
        captured['token'] = token

        class DummyApi:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return DummyApi()

    monkeypatch.setattr(cli, 'create_api', fake_create_api)

    args = SimpleNamespace(
        out_dir='.artifacts',
        skip_group_members=False,
        no_cache=False,
        no_report=False,
        open_report=False,
        token='from_arg',
    )

    code = cli.inventory_run(args)

    assert code == 0
    assert captured['token'] == 'from_arg'


def test_virtual_extensions_module_uses_list_range() -> None:
    from Space_OdT.modules.catalog import MODULE_SPECS

    spec = next(m for m in MODULE_SPECS if m.name == 'virtual_extensions')

    assert spec.list_path == 'telephony.virtual_extensions.list_range'
