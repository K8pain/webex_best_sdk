from __future__ import annotations

from pathlib import Path


def ensure_dirs(out_dir: Path) -> dict[str, Path]:
    exports = out_dir / 'exports'
    report = out_dir / 'report'
    exports.mkdir(parents=True, exist_ok=True)
    report.mkdir(parents=True, exist_ok=True)
    return {'out': out_dir, 'exports': exports, 'report': report}
