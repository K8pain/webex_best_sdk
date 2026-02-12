from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .config import ExportConfig
from .io.artifact_paths import csv_output_path, ensure_artifact_dir, json_output_path
from .io.csv_writer import write_csv
from .io.json_writer import write_json
from .modules import DomainCollector, default_collectors
from .status import ExportStatus, new_status, save_status, utc_now_iso


def run_export(
    *,
    api_client: Any,
    config: ExportConfig,
    collectors: Sequence[DomainCollector] | None = None,
    csv_writer: Callable = write_csv,
    json_writer: Callable = write_json,
    clock: Callable[[], str] = utc_now_iso,
) -> ExportStatus:
    ensure_artifact_dir(config.paths.artifacts_dir)
    active_collectors = list(collectors or default_collectors())
    status = new_status(clock)
    save_status(config.paths.status_file, status)

    try:
        for collector in active_collectors:
            rows = collector.collect(api_client)
            if config.toggles.write_csv:
                csv_writer(csv_output_path(config.paths.artifacts_dir, collector.domain), rows)
            if config.toggles.write_json:
                json_writer(json_output_path(config.paths.artifacts_dir, collector.domain), rows)
            status.domains[collector.domain] = "ok"

        status.state = "completed"
    except Exception as exc:
        status.state = "failed"
        status.error = str(exc)
        raise
    finally:
        status.finished_at = clock()
        save_status(config.paths.status_file, status)

    return status
