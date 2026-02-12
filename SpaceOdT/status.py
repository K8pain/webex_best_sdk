from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


@dataclass
class ExportStatus:
    started_at: str
    finished_at: str | None = None
    state: str = "running"
    domains: dict[str, str] = field(default_factory=dict)
    error: str | None = None


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def new_status(clock: Callable[[], str] = utc_now_iso) -> ExportStatus:
    return ExportStatus(started_at=clock())


def save_status(path: Path, status: ExportStatus) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(status), indent=2), encoding="utf-8")


def load_status(path: Path) -> ExportStatus | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ExportStatus(**payload)
