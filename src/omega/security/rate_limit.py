"""Small thread-safe sliding-window limiter for local denial-of-service resistance."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from time import monotonic


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: float = 0.0


class SlidingWindowRateLimiter:
    def __init__(
        self,
        maximum_events: int,
        window_seconds: float,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if (
            isinstance(maximum_events, bool)
            or not isinstance(maximum_events, int)
            or maximum_events <= 0
            or isinstance(window_seconds, bool)
            or not isinstance(window_seconds, (int, float))
            or window_seconds <= 0
        ):
            raise ValueError("Rate-limit bounds must be positive.")
        self.maximum_events = maximum_events
        self.window_seconds = float(window_seconds)
        self._clock = clock
        self._events: deque[float] = deque()
        self._lock = RLock()

    def acquire(self) -> RateLimitDecision:
        with self._lock:
            now = self._clock()
            boundary = now - self.window_seconds
            while self._events and self._events[0] <= boundary:
                self._events.popleft()
            if len(self._events) >= self.maximum_events:
                retry = max(0.0, self.window_seconds - (now - self._events[0]))
                return RateLimitDecision(False, retry)
            self._events.append(now)
            return RateLimitDecision(True)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
