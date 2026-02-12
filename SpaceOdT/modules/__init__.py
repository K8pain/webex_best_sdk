from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .people import collect_people
from .rooms import collect_rooms


@dataclass(frozen=True)
class DomainCollector:
    domain: str
    collect: Callable[[Any], list[dict[str, Any]]]


def default_collectors() -> list[DomainCollector]:
    return [
        DomainCollector(domain="rooms", collect=collect_rooms),
        DomainCollector(domain="people", collect=collect_people),
    ]
