"""Single process-local authority for exact, scoped confirmations."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import RLock
from time import monotonic
from uuid import UUID

from omega.core.exceptions import ModelValidationError
from omega.models import Action, ConfirmationStatus, UserCommand
from omega.models.result import ActionResult
from omega.safety.models import PendingConfirmation, ResourceFingerprint, SafetyContext

Executor = Callable[[], ActionResult]
Revalidator = Callable[[], ResourceFingerprint | None]


class ConfirmationOutcome(StrEnum):
    NOT_HANDLED = "not_handled"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    MISMATCH = "mismatch"
    ATTEMPTS_EXCEEDED = "attempts_exceeded"
    SESSION_MISMATCH = "session_mismatch"
    REPLAYED = "replayed"


@dataclass(frozen=True)
class ConfirmationMatch:
    outcome: ConfirmationOutcome
    pending: PendingConfirmation | None = None
    command: UserCommand | None = None
    action: Action | None = None
    executor: Executor | None = None
    revalidator: Revalidator | None = None
    original_fingerprint: ResourceFingerprint | None = None
    context: SafetyContext | None = None


@dataclass
class _PendingExecution:
    public: PendingConfirmation
    command: UserCommand
    action: Action
    executor: Executor
    revalidator: Revalidator
    expires_monotonic: float
    context: SafetyContext


class ConfirmationManager:
    """Allow one exact, expiring, action-bound confirmation per session."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30,
        maximum_attempts: int = 3,
        monotonic_clock: Callable[[], float] = monotonic,
        now_provider: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or timeout_seconds <= 0
            or timeout_seconds > 300
        ):
            raise ModelValidationError(
                "confirmation timeout must be positive and at most 300 seconds."
            )
        if (
            isinstance(maximum_attempts, bool)
            or not isinstance(maximum_attempts, int)
            or not 1 <= maximum_attempts <= 10
        ):
            raise ModelValidationError(
                "maximum confirmation attempts must be between 1 and 10."
            )
        self.timeout_seconds = float(timeout_seconds)
        self.maximum_attempts = maximum_attempts
        self._clock = monotonic_clock
        self._now = now_provider
        self._pending: dict[UUID, _PendingExecution] = {}
        self._consumed_commands: set[str] = set()
        self._lock = RLock()

    @property
    def pending(self) -> tuple[PendingConfirmation, ...]:
        with self._lock:
            self._expire_all()
            return tuple(item.public for item in self._pending.values())

    def get(self, session_id: UUID) -> PendingConfirmation | None:
        with self._lock:
            self._expire_all()
            item = self._pending.get(session_id)
            return item.public if item else None

    def create(
        self,
        *,
        session_id: UUID,
        command: UserCommand,
        action: Action,
        display_target: str,
        prompt: str,
        expected_confirmation: str,
        expected_cancellation: str,
        fingerprint: ResourceFingerprint | None,
        executor: Executor,
        revalidator: Revalidator,
        context: SafetyContext,
    ) -> tuple[PendingConfirmation, PendingConfirmation | None]:
        now = self._now().astimezone(UTC)
        public = PendingConfirmation(
            confirmation_id=secrets.token_urlsafe(18),
            session_id=session_id,
            command_id=command.command_id,
            action_id=action.action_id,
            intent=action.intent,
            target_fingerprint=fingerprint,
            display_target=display_target,
            prompt=prompt,
            expected_confirmation=self._normalize(expected_confirmation),
            expected_cancellation=self._normalize(expected_cancellation),
            created_at=now,
            expires_at=now + timedelta(seconds=self.timeout_seconds),
        )
        with self._lock:
            replaced = self._pending.pop(session_id, None)
            self._consumed_commands.discard(public.expected_confirmation)
            self._pending[session_id] = _PendingExecution(
                public,
                command,
                action,
                executor,
                revalidator,
                self._clock() + self.timeout_seconds,
                context,
            )
        return public, replaced.public if replaced else None

    def resolve(self, text: str, session_id: UUID | None) -> ConfirmationMatch:
        normalized = self._normalize(text)
        control_like = self._control_like(normalized)
        if not control_like:
            return ConfirmationMatch(ConfirmationOutcome.NOT_HANDLED)
        with self._lock:
            if normalized in self._consumed_commands:
                return ConfirmationMatch(ConfirmationOutcome.REPLAYED)
            if session_id is None or session_id not in self._pending:
                self._expire_all()
                if self._pending:
                    return ConfirmationMatch(ConfirmationOutcome.SESSION_MISMATCH)
                return ConfirmationMatch(ConfirmationOutcome.REPLAYED)
            item = self._pending[session_id]
            if self._clock() > item.expires_monotonic:
                self._pending.pop(session_id, None)
                return ConfirmationMatch(ConfirmationOutcome.EXPIRED, item.public)
            if normalized == item.public.expected_cancellation:
                self._pending.pop(session_id, None)
                cancelled = replace(item.public, status=ConfirmationStatus.REJECTED)
                return ConfirmationMatch(
                    ConfirmationOutcome.CANCELLED,
                    cancelled,
                    item.command,
                    item.action,
                )
            if normalized == item.public.expected_confirmation:
                self._pending.pop(session_id, None)
                self._consumed_commands.add(normalized)
                approved = replace(item.public, status=ConfirmationStatus.APPROVED)
                return ConfirmationMatch(
                    ConfirmationOutcome.APPROVED,
                    approved,
                    item.command,
                    item.action,
                    item.executor,
                    item.revalidator,
                    item.public.target_fingerprint,
                    item.context,
                )
            attempts = item.public.attempt_count + 1
            if attempts >= self.maximum_attempts:
                self._pending.pop(session_id, None)
                return ConfirmationMatch(
                    ConfirmationOutcome.ATTEMPTS_EXCEEDED,
                    replace(
                        item.public,
                        status=ConfirmationStatus.REJECTED,
                        attempt_count=attempts,
                    ),
                    item.command,
                    item.action,
                )
            item.public = replace(item.public, attempt_count=attempts)
            return ConfirmationMatch(
                ConfirmationOutcome.MISMATCH,
                item.public,
                item.command,
                item.action,
            )

    def clear(self, session_id: UUID | None = None) -> None:
        """Clear pending payloads without persisting or logging their contents."""
        with self._lock:
            if session_id is None:
                self._pending.clear()
            else:
                self._pending.pop(session_id, None)

    def _expire_all(self) -> None:
        now = self._clock()
        expired = [
            key for key, item in self._pending.items() if now > item.expires_monotonic
        ]
        for key in expired:
            self._pending.pop(key, None)

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.strip().split()).casefold()

    @staticmethod
    def _control_like(text: str) -> bool:
        return text in {
            "yes",
            "y",
            "confirm",
            "okay",
            "do it",
            "i approve",
        } or text.startswith(("confirm ", "cancel "))
