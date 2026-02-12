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
        'workspaces',
        'calling_locations',
        'calling_locations_details',
        'group_members',
        'license_assigned_users',
        'workspace_capabilities',
        'auto_attendants',
        'auto_attendant_details',
        'auto_attendant_announcement_files',
        'auto_attendant_forwarding',
        'hunt_groups',
        'hunt_group_details',
        'hunt_group_forwarding',
        'call_queues',
        'call_queue_details',
        'call_queue_settings',
        'call_queue_agents',
        'call_queue_forwarding',
        'virtual_lines',
        'virtual_line_details',
        'virtual_line_assigned_devices',
        'virtual_extensions',
        'virtual_extension_details',
        'virtual_extension_ranges',
        'virtual_extension_range_details',
        'person_numbers',
        'person_permissions_in',
        'person_permissions_out',
        'person_out_access_codes',
        'person_out_digit_patterns',
        'person_transfer_numbers',
        'workspace_permissions_in',
        'workspace_permissions_out',
        'workspace_devices',
        'person_available_numbers_available',
        'person_available_numbers_primary',
        'person_available_numbers_secondary',
        'person_available_numbers_call_forward',
        'person_available_numbers_call_intercept',
        'person_available_numbers_ecbn',
        'person_available_numbers_fax_message',
        'virtual_line_available_numbers_available',
        'virtual_line_available_numbers_primary',
        'virtual_line_available_numbers_secondary',
        'workspace_available_numbers_available',
        'workspace_available_numbers_primary',
        'workspace_available_numbers_secondary',
    ])


def exports_dir(settings: Settings) -> Path:
    return settings.out_dir / 'exports'


def report_dir(settings: Settings) -> Path:
    return settings.out_dir / 'report'
