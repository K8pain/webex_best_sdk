from __future__ import annotations

from pathlib import Path


def ensure_artifact_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def csv_output_path(artifacts_dir: Path, domain: str) -> Path:
    return artifacts_dir / f"{domain}.csv"


def json_output_path(artifacts_dir: Path, domain: str) -> Path:
    return artifacts_dir / f"{domain}.json"
