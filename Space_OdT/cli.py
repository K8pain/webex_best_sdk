from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import webbrowser
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from Space_OdT.config import Settings
    from Space_OdT.export_runner import run_exports
    from Space_OdT.sdk_client import MissingTokenError, create_api, resolve_access_token
else:
    from .config import Settings
    from .export_runner import run_exports
    from .sdk_client import MissingTokenError, create_api, resolve_access_token


LAB_FALLBACK_WEBEX_ACCESS_TOKEN = 'ZmI0ZmE0MDYtMGViYS00MDc0LWFhZGEtNThlNGYzOTVmMDE4ODMzZTJjOTUtZGZi_P0A1_e5f7d973-b269-4686-997e-45119168ced2'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Space_OdT deterministic Webex read-only exporter')
    parser.add_argument('command', choices=['inventory_run', 'v2_bulk_run', 'v21_softphone_bulk_run', 'v21_softphone_ui'])
    parser.add_argument('--out-dir', default='.artifacts')
    parser.add_argument('--no-report', action='store_true')
    parser.add_argument('--no-cache', action='store_true')
    parser.add_argument('--skip-group-members', action='store_true')
    parser.add_argument('--open-report', action='store_true', help='Open generated static HTML report in browser')
    parser.add_argument('--token', default=None, help='Explicit Webex access token (overrides .env and WEBEX_ACCESS_TOKEN)')
    parser.add_argument('--concurrent-requests', type=int, default=10)
    parser.add_argument('--only-failures', action='store_true')
    parser.add_argument('--debug-har', action='store_true')
    parser.add_argument('--decisions-file', default=None, help='JSON file with stage decisions to avoid interactive prompts')
    parser.add_argument('--v21-apply', action='store_true', help='For v2.1 run: apply mode (default is dry-run)')
    parser.add_argument('--v21-ui-host', default='127.0.0.1')
    parser.add_argument('--v21-ui-port', type=int, default=8765)
    return parser


def inventory_run(args) -> int:
    os.environ.setdefault('WEBEX_ACCESS_TOKEN', LAB_FALLBACK_WEBEX_ACCESS_TOKEN)

    settings = Settings(
        out_dir=Path(args.out_dir),
        include_group_members=not args.skip_group_members,
        write_cache=not args.no_cache,
        write_report=not args.no_report,
    )
    try:
        api = create_api(token=args.token)
    except MissingTokenError as exc:
        print(str(exc))
        return 2

    with api:
        summary = run_exports(api=api, settings=settings)

    print(f"Exports generated under {summary['exports_dir']}")
    if summary.get('report_path'):
        print(f"Static report: {summary['report_path']}")
        if args.open_report:
            webbrowser.open(Path(summary['report_path']).resolve().as_uri())
    for name, count in summary['module_counts'].items():
        print(f'- {name}: {count}')
    return 0


def _decision_provider_from_file(path: Path):
    from Space_OdT.v2.engine import parse_stage_decision

    payload = json.loads(path.read_text(encoding='utf-8'))

    def provider(stage):
        raw = str(payload.get(stage.value, 'yes'))
        return parse_stage_decision(raw)

    return provider


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == 'inventory_run':
        raise SystemExit(inventory_run(args))
    if args.command == 'v2_bulk_run':
        from Space_OdT.v2.engine import MissingV2InputsError, V2Runner

        try:
            token = resolve_access_token(args.token)
        except MissingTokenError as exc:
            raise SystemExit(str(exc))
        decision_provider = None
        if args.decisions_file:
            decision_provider = _decision_provider_from_file(Path(args.decisions_file))
        runner = V2Runner(
            token=token,
            out_dir=Path(args.out_dir),
            concurrent_requests=args.concurrent_requests,
            debug_har=args.debug_har,
            decision_provider=decision_provider,
        )
        try:
            summary = asyncio.run(runner.run(only_failures=args.only_failures))
        except MissingV2InputsError as exc:
            print(str(exc))
            raise SystemExit(2)
        print(f"V2 run completed: completed={summary['completed_count']} failed={summary['failed_count']}")
        raise SystemExit(0)


    if args.command == 'v21_softphone_ui':
        from Space_OdT.v21 import launch_v21_ui

        try:
            token = resolve_access_token(args.token)
        except MissingTokenError as exc:
            raise SystemExit(str(exc))
        launch_v21_ui(token=token, out_dir=Path(args.out_dir), host=args.v21_ui_host, port=args.v21_ui_port)
        raise SystemExit(0)

    if args.command == 'v21_softphone_bulk_run':
        from Space_OdT.v21.engine import MissingV21InputsError, V21Runner

        try:
            token = resolve_access_token(args.token)
        except MissingTokenError as exc:
            raise SystemExit(str(exc))
        runner = V21Runner(
            token=token,
            out_dir=Path(args.out_dir),
        )
        try:
            summary = asyncio.run(runner.run(dry_run=not args.v21_apply))
        except MissingV21InputsError as exc:
            print(str(exc))
            raise SystemExit(2)
        print(
            f"V2.1 run completed: mode={summary['mode']} "
            f"planned={summary['planned_count']} failed={summary['failed_count']}"
        )
        raise SystemExit(0)
    raise SystemExit(2)


if __name__ == '__main__':
    main()
