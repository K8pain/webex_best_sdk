from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path
    artifacts_dir: Path
    status_file: Path


@dataclass(frozen=True)
class Toggles:
    write_csv: bool = True
    write_json: bool = True


@dataclass(frozen=True)
class ExportConfig:
    paths: Paths
    toggles: Toggles


def _env_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config_from_env() -> ExportConfig:
    root = Path(os.getenv("SPACEODT_ROOT", Path.cwd())).resolve()
    artifacts_dir = Path(os.getenv("SPACEODT_ARTIFACTS_DIR", root / "artifacts")).resolve()
    status_file = Path(os.getenv("SPACEODT_STATUS_FILE", artifacts_dir / "status.json")).resolve()

    return ExportConfig(
        paths=Paths(root=root, artifacts_dir=artifacts_dir, status_file=status_file),
        toggles=Toggles(
            write_csv=_env_bool(os.getenv("SPACEODT_WRITE_CSV"), True),
            write_json=_env_bool(os.getenv("SPACEODT_WRITE_JSON"), True),
        ),
    )
