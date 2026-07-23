"""Explicit bounded scheduler worker with at-most-once local notifications."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Event, Lock, Thread
from typing import Protocol

from omega.core.exceptions import ModelValidationError
from omega.scheduling.configuration import SchedulingConfiguration
from omega.scheduling.models import DeliveryStatus, ScheduledItem
from omega.scheduling.recurrence import next_future_occurrence
from omega.scheduling.repository import ScheduleRepository


class ScheduleNotifier(Protocol):
    def notify(self, item: ScheduledItem) -> None: ...


class LoggingNotifier:
    """Compatibility notifier for deployments without a presentation adapter."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def notify(self, item: ScheduledItem) -> None:
        self.logger.info("Scheduled %s is due.", item.schedule_type.value)


class SchedulerEngine:
    """Poll due occurrences only after an explicit ``start`` call."""

    def __init__(
        self,
        configuration: SchedulingConfiguration,
        repository: ScheduleRepository,
        notifier: ScheduleNotifier,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        logger: logging.Logger | None = None,
    ) -> None:
        self.configuration = configuration
        self.repository = repository
        self.notifier = notifier
        self.clock = clock
        self.logger = logger or logging.getLogger("omega.scheduling")
        self._stop = Event()
        self._thread: Thread | None = None
        self._lifecycle_lock = Lock()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lifecycle_lock:
            if not self.configuration.enabled or self.running:
                return
            self._stop.clear()
            self._recover_stale()
            self._thread = Thread(
                target=self._run,
                name="omega-scheduler",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lifecycle_lock:
            thread = self._thread
            if thread is None:
                return
            self._stop.set()
            thread.join(timeout=5)
            self._thread = None

    def run_once(self) -> int:
        now = self._now()
        self._recover_stale(now)
        delivered = 0
        claims = self.repository.claim_due(
            now,
            self.configuration.maximum_delivery_batch,
        )
        for claim in claims:
            item = claim.item
            age = (now - claim.occurrence_at_utc).total_seconds()
            status = DeliveryStatus.DELIVERED
            error_code: str | None = None
            should_deliver = (
                self.configuration.deliver_overdue_items
                and age <= self.configuration.maximum_overdue_age_seconds
            )
            if not should_deliver:
                status = DeliveryStatus.MISSED
                error_code = "OVERDUE_OCCURRENCE"
            else:
                try:
                    self.notifier.notify(item)
                    delivered += 1
                except Exception:
                    status = DeliveryStatus.FAILED
                    error_code = "NOTIFICATION_FAILED"
                    self.logger.exception(
                        "Schedule notification failed and will not be retried."
                    )
            next_due, count = (
                next_future_occurrence(
                    claim.occurrence_at_utc,
                    item.recurrence,
                    item.occurrence_count,
                    now,
                    item.timezone_name,
                )
                if item.recurrence
                else (None, item.occurrence_count + 1)
            )
            self.repository.finalize_claim(
                claim,
                now,
                status,
                next_due=next_due,
                occurrence_count=count,
                error_code=error_code,
            )
        return delivered

    def _recover_stale(self, now: datetime | None = None) -> int:
        if not self.configuration.restore_pending_items_on_startup:
            return 0
        return self.repository.recover_stale_claims(
            now or self._now(),
            timeout_seconds=self.configuration.claim_timeout_seconds,
            limit=self.configuration.maximum_delivery_batch,
        )

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ModelValidationError("Scheduler clocks must be timezone-aware.")
        return value.astimezone(UTC)

    def _run(self) -> None:
        while not self._stop.wait(self.configuration.scheduler_poll_interval_seconds):
            try:
                self.run_once()
            except Exception:
                self.logger.exception("Scheduler iteration failed safely.")
