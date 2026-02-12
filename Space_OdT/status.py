from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Callable

from wxc_sdk.rest import RestError


@dataclass
class StatusRecord:
    module: str
    method: str
    result: str
    http_status: int | None
    error: str
    count: int
    elapsed_ms: int


class StatusRecorder:
    def __init__(self) -> None:
        self.records: list[StatusRecord] = []

    def add(self, record: StatusRecord) -> None:
        self.records.append(record)

    def as_rows(self) -> list[dict]:
        return [asdict(r) for r in self.records]


def classify_exception(exc: Exception) -> tuple[str, int | None, str]:
    if isinstance(exc, RestError) and exc.response is not None:
        status = exc.response.status_code
        if status == 403:
            return 'forbidden', status, str(exc)
        if status == 404:
            return 'not_found', status, str(exc)
        return 'error', status, str(exc)
    return 'error', None, str(exc)


def timed_call(fn: Callable, *args, **kwargs):
    start = perf_counter()
    value = fn(*args, **kwargs)
    elapsed_ms = int((perf_counter() - start) * 1000)
    return value, elapsed_ms
