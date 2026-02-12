from __future__ import annotations

import argparse

from .config import load_config_from_env
from .export_runner import run_export
from .sdk_client import build_sdk_client


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SpaceOdT export runner")
    parser.add_argument("--token", help="Webex access token. Defaults to WEBEX_ACCESS_TOKEN.", default=None)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = load_config_from_env()
    api_client = build_sdk_client(token=args.token)
    run_export(api_client=api_client, config=config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
