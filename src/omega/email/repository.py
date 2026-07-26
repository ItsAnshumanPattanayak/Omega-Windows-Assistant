"""Minimal SQLite operation receipts for duplicate-send protection."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol

from omega.database.connection import DatabaseConnectionFactory
from omega.email.models import EmailOperationStatus


class EmailOperationStore(Protocol):
    def claim(
        self, operation_id: str, account_name: str, operation_type: str, target_id: str
    ) -> bool: ...

    def finish(
        self,
        operation_id: str,
        status: EmailOperationStatus,
        provider_reference: str | None = None,
    ) -> None: ...


@dataclass(frozen=True)
class OperationRecord:
    operation_id: str
    status: EmailOperationStatus
    provider_reference: str | None


class InMemoryEmailOperationStore:
    """Process-local receipt store for isolated domain tests."""

    def __init__(self) -> None:
        self.records: dict[str, OperationRecord] = {}
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
            self.records[operation_id] = OperationRecord(
                operation_id, EmailOperationStatus.PENDING, None
            )
            return True

    def finish(
        self,
        operation_id: str,
        status: EmailOperationStatus,
        provider_reference: str | None = None,
    ) -> None:
        with self._lock:
            self.records[operation_id] = OperationRecord(
                operation_id, status, provider_reference
            )


class SqliteEmailOperationStore:
    """Persist metadata-only idempotency receipts; content is never stored."""

    def __init__(self, connection_factory: DatabaseConnectionFactory) -> None:
        self.connection_factory = connection_factory

    def claim(
        self, operation_id: str, account_name: str, operation_type: str, target_id: str
    ) -> bool:
        now = datetime.now(UTC).isoformat()
        connection = self.connection_factory.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT status FROM email_operations "
                "WHERE account_name=? AND operation_type=? AND target_id=?",
                (account_name, operation_type, target_id),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                return False
            connection.execute(
                "INSERT INTO email_operations("
                "operation_id,account_name,operation_type,target_id,status,"
                "provider_reference,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    operation_id,
                    account_name,
                    operation_type,
                    target_id,
                    EmailOperationStatus.PENDING.value,
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
        status: EmailOperationStatus,
        provider_reference: str | None = None,
    ) -> None:
        connection = self.connection_factory.connect()
        try:
            with connection:
                connection.execute(
                    "UPDATE email_operations SET status=?,provider_reference=?,"
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
