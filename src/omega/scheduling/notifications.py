"""Thread-safe, bounded delivery of local schedule notifications."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol
from uuid import UUID

from omega.scheduling.models import ScheduledItem, ScheduleType


class NotificationSpeaker(Protocol):
    def speak(self, text: str) -> bool: ...


@dataclass(frozen=True)
class ScheduleNotification:
    """Safe presentation data for one due schedule."""

    schedule_id: UUID
    schedule_type: ScheduleType
    title: str
    message: str
    occurred_at: datetime


class NotificationCenter:
    """Fan-in notifier whose consumers explicitly drain bounded messages."""

    def __init__(
        self,
        logger: logging.Logger,
        *,
        maximum_pending: int = 100,
        speech_enabled: bool = False,
    ) -> None:
        if isinstance(maximum_pending, bool) or not 1 <= maximum_pending <= 1000:
            raise ValueError("maximum_pending must be between 1 and 1000.")
        self.logger = logger
        self.speech_enabled = speech_enabled
        self._speaker: NotificationSpeaker | None = None
        self._pending: deque[ScheduleNotification] = deque(maxlen=maximum_pending)
        self._lock = Lock()

    def notify(self, item: ScheduledItem) -> None:
        notification = ScheduleNotification(
            item.schedule_id,
            item.schedule_type,
            item.title,
            item.message,
            datetime.now(UTC),
        )
        with self._lock:
            self._pending.append(notification)
        self.logger.info("Scheduled %s is due.", item.schedule_type.value)
        speaker = self._speaker
        if self.speech_enabled and speaker is not None:
            try:
                if not speaker.speak(f"{item.title}. {item.message}"):
                    self.logger.warning("Optional schedule speech was unavailable.")
            except Exception:
                self.logger.exception("Optional schedule speech failed safely.")

    def set_speaker(self, speaker: NotificationSpeaker | None) -> None:
        """Attach only an explicitly initialized local speech adapter."""

        with self._lock:
            self._speaker = speaker

    def drain(self, limit: int = 20) -> tuple[ScheduleNotification, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        values: list[ScheduleNotification] = []
        with self._lock:
            while self._pending and len(values) < limit:
                values.append(self._pending.popleft())
        return tuple(values)
