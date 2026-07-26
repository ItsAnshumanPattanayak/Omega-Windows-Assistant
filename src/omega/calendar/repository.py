"""Metadata-only calendar mutation receipts."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol

from omega.calendar.models import CalendarOperationStatus
from omega.database.connection import DatabaseConnectionFactory


class CalendarOperationStore(Protocol):
    def claim(
        self, operation_id: str, account_name: str, operation_type: str, target_id: str
    ) -> bool: ...
    def finish(
        self,
        operation_id: str,
        status: CalendarOperationStatus,
        provider_reference: str | None = None,
    ) -> None: ...


class InMemoryCalendarOperationStore:
    def __init__(self) -> None:
        self.records: dict[str, tuple[CalendarOperationStatus, str | None]] = {}
        self.targets: set[tuple[str, str, str]] = set()
        self._lock = RLock()

    def claim(
        self, operation_id: str, account_name: str, operation_type: str, target_id: str
    ) -> bool:
        key = (account_name, operation_type, target_id)
        with self._lock:
            if key in self.targets:
                return False
            self.targets.add(key)
            self.records[operation_id] = (CalendarOperationStatus.PENDING, None)
            return True

    def finish(
        self,
        operation_id: str,
        status: CalendarOperationStatus,
        provider_reference: str | None = None,
    ) -> None:
        with self._lock:
            self.records[operation_id] = (status, provider_reference)


class SqliteCalendarOperationStore:
    def __init__(self, connection_factory: DatabaseConnectionFactory) -> None:
        self.connection_factory = connection_factory

    def claim(
        self, operation_id: str, account_name: str, operation_type: str, target_id: str
    ) -> bool:
        now = datetime.now(UTC).isoformat()
        connection = self.connection_factory.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            found = connection.execute(
                "SELECT 1 FROM calendar_operations "
                "WHERE account_name=? AND operation_type=? AND target_id=?",
                (account_name, operation_type, target_id),
            ).fetchone()
            if found:
                connection.rollback()
                return False
            connection.execute(
                "INSERT INTO calendar_operations VALUES(?,?,?,?,?,?,?,?)",
                (
                    operation_id,
                    account_name,
                    operation_type,
                    target_id,
                    CalendarOperationStatus.PENDING.value,
                    None,
                    now,
                    now,
                ),
            )
            connection.commit()
            return True
        except sqlite3.Error:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def finish(
        self,
        operation_id: str,
        status: CalendarOperationStatus,
        provider_reference: str | None = None,
    ) -> None:
        connection = self.connection_factory.connect()
        try:
            with connection:
                connection.execute(
                    "UPDATE calendar_operations SET status=?,provider_reference=?,"
                    "updated_at=? WHERE operation_id=?",
                    (
                        status.value,
                        provider_reference,
                        datetime.now(UTC).isoformat(),
                        operation_id,
                    ),
                )
        finally:
            connection.close()
