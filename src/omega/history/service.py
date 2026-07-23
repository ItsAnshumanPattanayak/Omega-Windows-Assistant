"""Cohesive, non-executing persistent history operations."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from omega.core.exceptions import HistoryCleanupError, HistoryExportError
from omega.database import ActionRepository, CommandRepository
from omega.database.connection import DatabaseConnectionFactory
from omega.models import Action, ActionResult, ActionStatus, UserCommand
from omega.recovery import RecoveryRecord, RecoveryRecordStatus
from omega.recovery.store import RecoveryRecordStore


@dataclass(frozen=True)
class RetryEligibility:
    action_id: UUID
    eligible: bool
    reason_code: str
    user_message: str


@dataclass(frozen=True)
class HistoryCleanupSummary:
    commands: int
    actions: int
    results: int
    recovery_records: int


@dataclass(frozen=True)
class HistoryExportResult:
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class HistoryActivity:
    kind: str
    identifier: UUID
    occurred_at: datetime
    summary: str


class HistoryService:
    """Compose existing repositories for bounded history reads and maintenance."""

    EXPORT_VERSION = 1

    def __init__(
        self,
        connection_factory: DatabaseConnectionFactory,
        commands: CommandRepository,
        actions: ActionRepository,
        recovery: RecoveryRecordStore,
        *,
        default_limit: int = 20,
        maximum_limit: int = 100,
        maximum_export_bytes: int = 1_048_576,
        export_root: Path | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.commands = commands
        self.actions = actions
        self.recovery = recovery
        self.default_limit = self._validate_positive(default_limit, 1000)
        self.maximum_limit = self._validate_positive(maximum_limit, 1000)
        if self.default_limit > self.maximum_limit:
            raise ValueError("default history limit exceeds maximum.")
        self.maximum_export_bytes = self._validate_positive(
            maximum_export_bytes, 50_000_000
        )
        self.export_root = export_root or Path.cwd() / "data" / "history_exports"

    def recent_commands(self, limit: int | None = None) -> tuple[UserCommand, ...]:
        return tuple(self.commands.list_recent(limit=self._limit(limit)))

    def recent_actions(self, limit: int | None = None) -> tuple[Action, ...]:
        return tuple(self.actions.list_recent(limit=self._limit(limit)))

    def actions_for_command(
        self, command_id: UUID, limit: int | None = None
    ) -> tuple[Action, ...]:
        return tuple(
            self.actions.list_for_command(command_id, limit=self._limit(limit))
        )

    def result_for_action(self, action_id: UUID) -> ActionResult | None:
        return self.actions.get_result(action_id)

    def failed_actions(self, limit: int | None = None) -> tuple[Action, ...]:
        requested = self._limit(limit)
        actions = self.actions.list_recent(limit=self.maximum_limit)
        return tuple(
            action for action in actions if action.status is ActionStatus.FAILED
        )[:requested]

    def latest_activity(self, limit: int | None = None) -> tuple[HistoryActivity, ...]:
        requested = self._limit(limit)
        items = [
            HistoryActivity(
                "command",
                command.command_id,
                command.received_at,
                command.original_text,
            )
            for command in self.commands.list_recent(limit=requested)
        ]
        items.extend(
            HistoryActivity(
                "action",
                action.action_id,
                action.created_at,
                f"{action.intent.value}: {action.status.value}",
            )
            for action in self.actions.list_recent(limit=requested)
        )
        items.sort(
            key=lambda item: (item.occurred_at, str(item.identifier)), reverse=True
        )
        return tuple(items[:requested])

    def active_undo_records(self) -> tuple[RecoveryRecord, ...]:
        now = datetime.now(UTC)
        return tuple(
            record
            for record in self.recovery.list_newest_first()
            if record.status is RecoveryRecordStatus.COMPLETED
            and (record.expires_at is None or record.expires_at > now)
        )

    def retry_eligibility(self, action_id: UUID) -> RetryEligibility:
        action = self.actions.get(action_id)
        if action is None:
            return RetryEligibility(
                action_id, False, "ACTION_NOT_FOUND", "That action was not found."
            )
        result = self.actions.get_result(action_id)
        if result is None or result.success:
            return RetryEligibility(
                action_id,
                False,
                "NOT_FAILED",
                "Only a recorded failed action can be considered for retry.",
            )
        if result.error is None or not result.error.recoverable:
            return RetryEligibility(
                action_id,
                False,
                "NOT_RECOVERABLE",
                "That failure is not eligible for retry.",
            )
        return RetryEligibility(
            action_id,
            True,
            "RETRY_ELIGIBLE",
            "The action may be submitted again as a new command after safety review.",
        )

    def cleanup(
        self,
        *,
        before: datetime | None = None,
        remove_active_undo: bool = False,
    ) -> HistoryCleanupSummary:
        cutoff = before.astimezone(UTC).isoformat() if before else None
        active = self.active_undo_records()
        if active and not remove_active_undo:
            raise HistoryCleanupError(
                "Active undo records must be preserved during history cleanup."
            )
        connection = self.connection_factory.connect()
        try:
            with connection:
                where = " WHERE received_at < ?" if cutoff else ""
                parameters = (cutoff,) if cutoff else ()
                results = int(
                    connection.execute(
                        f"""
                        SELECT COUNT(*) FROM action_results
                        WHERE action_id IN (
                            SELECT action_id FROM actions
                            WHERE command_id IN (
                                SELECT command_id FROM commands{where}
                            )
                        )
                        """,
                        parameters,
                    ).fetchone()[0]
                )
                actions = int(
                    connection.execute(
                        f"""
                        SELECT COUNT(*) FROM actions
                        WHERE command_id IN (
                            SELECT command_id FROM commands{where}
                        )
                        """,
                        parameters,
                    ).fetchone()[0]
                )
                commands = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM commands{where}", parameters
                    ).fetchone()[0]
                )
                recovery = int(
                    connection.execute(
                        f"""
                        SELECT COUNT(*) FROM recovery_records
                        WHERE command_id IN (
                            SELECT command_id FROM commands{where}
                        )
                        """,
                        parameters,
                    ).fetchone()[0]
                )
                connection.execute(f"DELETE FROM commands{where}", parameters)
        except sqlite3.Error as error:
            raise HistoryCleanupError(
                "Omega could not clean history transactionally."
            ) from error
        finally:
            connection.close()
        return HistoryCleanupSummary(commands, actions, results, recovery)

    def serialize_json(self, limit: int | None = None) -> str:
        requested = self._limit(limit)
        commands = self.recent_commands(requested)
        actions = self.recent_actions(requested)
        payload = {
            "export_version": self.EXPORT_VERSION,
            "schema_version": 5,
            "exported_at": datetime.now(UTC).isoformat(),
            "commands": [command.to_dict() for command in commands],
            "actions": [action.to_dict() for action in actions],
            "action_results": [
                result.to_dict()
                for action in actions
                if (result := self.actions.get_result(action.action_id)) is not None
            ],
            "recovery_records": [
                record.to_dict()
                for record in self.recovery.list_newest_first()[:requested]
            ],
        }
        encoded = json.dumps(
            self._redact(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(encoded.encode("utf-8")) > self.maximum_export_bytes:
            raise HistoryExportError("The history export exceeds its configured limit.")
        return encoded

    def export_json(self, filename: str = "omega-history.json") -> HistoryExportResult:
        candidate = Path(filename)
        if (
            candidate.is_absolute()
            or len(candidate.parts) != 1
            or candidate.suffix.casefold() != ".json"
        ):
            raise HistoryExportError("History exports require one safe JSON filename.")
        target = self.export_root / candidate.name
        if target.exists():
            raise HistoryExportError("The history export already exists.")
        data = self.serialize_json().encode("utf-8")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except OSError as error:
            raise HistoryExportError(
                "Omega could not write the history export."
            ) from error
        return HistoryExportResult(target, len(data))

    def _limit(self, value: int | None) -> int:
        selected = self.default_limit if value is None else value
        return self._validate_positive(selected, self.maximum_limit)

    @classmethod
    def _redact(cls, value: object) -> object:
        if isinstance(value, dict):
            return {
                str(key): (
                    "[REDACTED]"
                    if any(
                        marker in str(key).casefold()
                        for marker in (
                            "password",
                            "token",
                            "secret",
                            "traceback",
                            "stack",
                        )
                    )
                    else cls._redact(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._redact(item) for item in value]
        if isinstance(value, str):
            return re.sub(
                r"(?i)\b(password|token|secret)\s*[:=]\s*\S+",
                r"\1=[REDACTED]",
                value,
            )
        return value

    @staticmethod
    def _validate_positive(value: int, maximum: int) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= maximum
        ):
            raise ValueError(f"limit must be between 1 and {maximum}.")
        return value
