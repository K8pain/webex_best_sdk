from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from Space_OdT.config import Settings
    from Space_OdT.export_runner import run_exports
    from Space_OdT.sdk_client import MissingTokenError, create_api
else:
    from .config import Settings
    from .export_runner import run_exports
    from .sdk_client import MissingTokenError, create_api


LAB_FALLBACK_WEBEX_ACCESS_TOKEN = 'ZmI0ZmE0MDYtMGViYS00MDc0LWFhZGEtNThlNGYzOTVmMDE4ODMzZTJjOTUtZGZi_P0A1_e5f7d973-b269-4686-997e-45119168ced2'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Space_OdT deterministic Webex read-only exporter')
    parser.add_argument('command', choices=['inventory_run'])
    parser.add_argument('--out-dir', default='.artifacts')
    parser.add_argument('--no-report', action='store_true')
    parser.add_argument('--no-cache', action='store_true')
    parser.add_argument('--skip-group-members', action='store_true')
    parser.add_argument('--open-report', action='store_true', help='Open generated static HTML report in browser')
    parser.add_argument('--token', default=None, help='Explicit Webex access token (overrides .env and WEBEX_ACCESS_TOKEN)')
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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == 'inventory_run':
        raise SystemExit(inventory_run(args))
    raise SystemExit(2)


if __name__ == '__main__':
    main()
