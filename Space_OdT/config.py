from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    out_dir: Path = Path('.artifacts')
    include_group_members: bool = True
    write_cache: bool = True
    write_report: bool = True
    enabled_modules: list[str] = field(default_factory=lambda: [
        'people',
        'groups',
        'locations',
        'licenses',
        'call_queues',
        'hunt_groups',
        'auto_attendants',
        'virtual_lines',
        'virtual_extensions',
        'schedules',
        'pstn_locations',
        'devices',
        'workspaces',
    ])


def exports_dir(settings: Settings) -> Path:
    return settings.out_dir / 'exports'


def report_dir(settings: Settings) -> Path:
    return settings.out_dir / 'report'
