"""Bounded local timing metrics that never include command or content values."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock
from time import perf_counter


@dataclass(frozen=True, slots=True)
class TimingRecord:
    operation: str
    duration_ms: float


class LocalTimingMetrics:
    def __init__(self, *, enabled: bool, maximum_records: int) -> None:
        if maximum_records <= 0:
            raise ValueError("maximum_records must be positive")
        self.enabled = enabled
        self._records: deque[TimingRecord] = deque(maxlen=maximum_records)
        self._lock = RLock()

    def record(self, operation: str, started_at: float) -> None:
        if not self.enabled:
            return
        if not operation.isidentifier() or len(operation) > 80:
            raise ValueError("operation must be a safe identifier")
        elapsed = max(0.0, (perf_counter() - started_at) * 1_000)
        with self._lock:
            self._records.append(TimingRecord(operation, elapsed))

    def snapshot(self) -> tuple[TimingRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
