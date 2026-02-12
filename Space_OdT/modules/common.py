from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass
class ModuleResult:
    module: str
    method: str
    rows: list[dict]
    count: int
    raw_keys: list[str]


def model_to_dict(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    dump = getattr(value, 'model_dump', None)
    if callable(dump):
        return dump(by_alias=False, exclude_none=True)
    return dict(value.__dict__) if hasattr(value, '__dict__') else {}


def as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        return list(value)
    return [value]


def resolve_attr(root: Any, dotted: str) -> Any:
    current = root
    for part in dotted.split('.'):
        current = getattr(current, part)
    return current


def call_with_supported_kwargs(fn, **kwargs):
    sig = inspect.signature(fn)
    accepted = {k: v for k, v in kwargs.items() if k in sig.parameters and v is not None}
    return fn(**accepted)


def first_id(rows: list[dict]) -> str | None:
    for row in rows:
        for key in ('id', 'person_id', 'group_id', 'location_id', 'license_id', 'workspace_id', 'device_id'):
            if row.get(key):
                return str(row[key])
    return None


def details_keys(details_obj: Any) -> list[str]:
    return sorted(model_to_dict(details_obj).keys())
