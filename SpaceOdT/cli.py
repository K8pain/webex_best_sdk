from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_OUT_DIR = ".artifacts"
DEFAULT_REPORT_NAME = "report.json"
FIXED_MODULES: tuple[str, ...] = (
    "organizations",
    "locations",
    "people",
    "groups",
    "group_members",
)


@dataclass(frozen=True)
class ModuleExportResult:
    module: str
    result: str
    count: int
    file_paths: tuple[str, ...]


class MissingTokenError(RuntimeError):
    """Raised when no API token is found in environment."""


def resolve_token(env: dict[str, str] | None = None) -> str:
    env_data = env or os.environ
    token = env_data.get("WEBEX_ACCESS_TOKEN") or env_data.get("WEBEX_TOKEN")
    if not token:
        raise MissingTokenError(
            "Missing Webex token. Set WEBEX_ACCESS_TOKEN (or WEBEX_TOKEN) before running this command."
        )
    return token


def module_list(skip_group_members: bool) -> list[str]:
    if not skip_group_members:
        return list(FIXED_MODULES)
    return [module for module in FIXED_MODULES if module != "group_members"]


def export_module(module: str, out_dir: Path, token: str) -> ModuleExportResult:
    del token  # token is validated once and reserved for future API calls.
    output_path = out_dir / f"{module}.json"
    payload = {
        "module": module,
        "items": [],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ModuleExportResult(
        module=module,
        result="ok",
        count=len(payload["items"]),
        file_paths=(str(output_path),),
    )


def run_exports(*, out_dir: Path, no_report: bool, skip_group_members: bool, env: dict[str, str] | None = None) -> list[ModuleExportResult]:
    token = resolve_token(env)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = [export_module(module=module, out_dir=out_dir, token=token) for module in module_list(skip_group_members)]

    if not no_report:
        report_path = out_dir / DEFAULT_REPORT_NAME
        report_payload = {
            "modules": [asdict(result) for result in results],
            "total_modules": len(results),
            "total_items": sum(result.count for result in results),
        }
        report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return results


def format_summary_line(result: ModuleExportResult) -> str:
    files = ", ".join(result.file_paths)
    return f"{result.module} -> {result.result} -> {result.count} -> {files}"


def print_summary(results: Iterable[ModuleExportResult]) -> None:
    for result in results:
        print(format_summary_line(result))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spaceodt", description="CLI para exportes SpaceOdT")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_all = subparsers.add_parser(
        "export-all",
        help="Ejecuta exportes de todos los módulos de la lista fija",
    )
    export_all.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Directorio de salida de artefactos")
    export_all.add_argument("--no-report", action="store_true", help="No generar reporte consolidado")
    export_all.add_argument(
        "--skip-group-members",
        action="store_true",
        help="Saltar export del módulo group_members",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "export-all":
        parser.error(f"Unknown command: {args.command}")

    try:
        results = run_exports(
            out_dir=Path(args.out_dir),
            no_report=bool(args.no_report),
            skip_group_members=bool(args.skip_group_members),
        )
    except MissingTokenError as exc:
        print(f"Error: {exc}")
        return 2

    print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
