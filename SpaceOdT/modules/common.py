from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def safe_iterable_rows(items: Iterable[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, "model_dump"):
            rows.append(item.model_dump())
        elif hasattr(item, "__dict__"):
            rows.append(dict(item.__dict__))
        else:
            rows.append({"value": str(item)})
    return rows
