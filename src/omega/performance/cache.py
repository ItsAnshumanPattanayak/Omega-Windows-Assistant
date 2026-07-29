"""Small thread-safe LRU storage for explicitly non-sensitive immutable data."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(frozen=True, slots=True)
class CacheStatistics:
    size: int
    maximum_size: int
    hits: int
    misses: int
    evictions: int


class BoundedLruCache(Generic[K, V]):
    """Bounded process-local cache with explicit clearing and no persistence."""

    def __init__(self, maximum_size: int) -> None:
        if isinstance(maximum_size, bool) or not isinstance(maximum_size, int):
            raise ValueError("maximum_size must be an integer")
        if not 0 <= maximum_size <= 10_000:
            raise ValueError("maximum_size must be between 0 and 10000")
        self.maximum_size = maximum_size
        self._values: OrderedDict[K, V] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._lock = RLock()

    def get(self, key: K) -> V | None:
        with self._lock:
            value = self._values.get(key)
            if value is None:
                self._misses += 1
                return None
            self._values.move_to_end(key)
            self._hits += 1
            return value

    def put(self, key: K, value: V) -> None:
        if self.maximum_size == 0:
            return
        with self._lock:
            self._values[key] = value
            self._values.move_to_end(key)
            while len(self._values) > self.maximum_size:
                self._values.popitem(last=False)
                self._evictions += 1

    def invalidate(self, key: K) -> None:
        with self._lock:
            self._values.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()

    def statistics(self) -> CacheStatistics:
        with self._lock:
            return CacheStatistics(
                len(self._values),
                self.maximum_size,
                self._hits,
                self._misses,
                self._evictions,
            )
