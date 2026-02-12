from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

from .config import Settings
from .export_runner import run_exports
from .sdk_client import MissingTokenError, create_api


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Space_OdT deterministic Webex read-only exporter')
    parser.add_argument('command', choices=['inventory_run'])
    parser.add_argument('--out-dir', default='.artifacts')
    parser.add_argument('--no-report', action='store_true')
    parser.add_argument('--no-cache', action='store_true')
    parser.add_argument('--skip-group-members', action='store_true')
    parser.add_argument('--open-report', action='store_true', help='Open generated static HTML report in browser')
    return parser


def inventory_run(args) -> int:
    settings = Settings(
        out_dir=Path(args.out_dir),
        include_group_members=not args.skip_group_members,
        write_cache=not args.no_cache,
        write_report=not args.no_report,
    )
    try:
        api = create_api()
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
