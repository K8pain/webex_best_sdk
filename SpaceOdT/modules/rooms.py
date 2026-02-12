from __future__ import annotations

from typing import Any

from .common import safe_iterable_rows


def collect_rooms(api: Any) -> list[dict[str, Any]]:
    return safe_iterable_rows(api.rooms.list())
