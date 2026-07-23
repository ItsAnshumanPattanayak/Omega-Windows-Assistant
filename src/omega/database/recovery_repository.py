"""SQLite-backed recovery records compatible with the Phase 8 registry."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from omega.core.exceptions import ModelValidationError, RecoveryRecordError
from omega.database.connection import DatabaseConnectionFactory
from omega.models._serialization import parse_utc_timestamp, validate_utc_timestamp
from omega.recovery.models import (
    RecoverableActionType,
    RecoveryRecord,
    RecoveryRecordStatus,
    RecoveryResourceType,
    RecycleBinItem,
)

_COLUMNS = """
record_id, action_type, resource_type, command_id, action_id, session_id,
display_name, logical_location, relative_path, original_path_fingerprint,
recycle_bin_reference, size_bytes, recycled_at, item_metadata_json, status,
created_at, expires_at, restored_at, failure_code, metadata_json
"""


class SqliteRecoveryRecordStore:
    """Persist bounded recovery records without touching user resources."""

    def __init__(
        self, connection_factory: DatabaseConnectionFactory, maximum_records: int
    ) -> None:
        if (
            isinstance(maximum_records, bool)
            or not isinstance(maximum_records, int)
            or maximum_records <= 0
        ):
            raise RecoveryRecordError("maximum_records must be a positive integer.")
        self.connection_factory = connection_factory
        self._maximum_records = maximum_records

    @property
    def maximum_records(self) -> int:
        return self._maximum_records

    def __len__(self) -> int:
        connection = self.connection_factory.connect()
        try:
            row = connection.execute("SELECT COUNT(*) FROM recovery_records").fetchone()
            return int(row[0]) if row else 0
        finally:
            connection.close()

    def add(self, record: RecoveryRecord) -> RecoveryRecord:
        connection = self.connection_factory.connect()
        try:
            with connection:
                connection.execute(
                    f"""
                    INSERT INTO recovery_records ({_COLUMNS})
                    VALUES ({",".join("?" for _ in range(20))})
                    ON CONFLICT(record_id) DO UPDATE SET
                        status=excluded.status,
                        expires_at=excluded.expires_at,
                        restored_at=excluded.restored_at,
                        failure_code=excluded.failure_code,
                        metadata_json=excluded.metadata_json
                    """,
                    self._serialize(record),
                )
                self._trim(connection)
        except sqlite3.Error as error:
            raise RecoveryRecordError(
                "Omega could not persist the recovery record."
            ) from error
        finally:
            connection.close()
        return record

    def get(self, record_id: UUID) -> RecoveryRecord | None:
        self._validate_id(record_id)
        connection = self.connection_factory.connect()
        try:
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM recovery_records WHERE record_id = ?",
                (str(record_id),),
            ).fetchone()
        except sqlite3.Error as error:
            raise RecoveryRecordError(
                "Omega could not read the recovery record."
            ) from error
        finally:
            connection.close()
        return None if row is None else self._deserialize(row)

    def require(self, record_id: UUID) -> RecoveryRecord:
        record = self.get(record_id)
        if record is None:
            raise RecoveryRecordError("The requested recovery record was not found.")
        return record

    def update(self, record: RecoveryRecord) -> RecoveryRecord:
        if self.get(record.record_id) is None:
            raise RecoveryRecordError("Cannot update an unknown recovery record.")
        return self.add(record)

    def remove(self, record_id: UUID) -> RecoveryRecord | None:
        record = self.get(record_id)
        if record is None:
            return None
        connection = self.connection_factory.connect()
        try:
            with connection:
                connection.execute(
                    "DELETE FROM recovery_records WHERE record_id = ?",
                    (str(record_id),),
                )
        except sqlite3.Error as error:
            raise RecoveryRecordError(
                "Omega could not remove the recovery record."
            ) from error
        finally:
            connection.close()
        return record

    def list_records(self) -> tuple[RecoveryRecord, ...]:
        return self._list("created_at ASC, record_id ASC")

    def list_newest_first(self) -> tuple[RecoveryRecord, ...]:
        return self._list("created_at DESC, record_id DESC")

    def replace_all(
        self, records: Iterable[RecoveryRecord]
    ) -> tuple[RecoveryRecord, ...]:
        supplied = tuple(records)
        if not all(isinstance(record, RecoveryRecord) for record in supplied):
            raise RecoveryRecordError(
                "All supplied records must be RecoveryRecord instances."
            )
        connection = self.connection_factory.connect()
        try:
            with connection:
                connection.execute("DELETE FROM recovery_records")
                for record in supplied:
                    connection.execute(
                        f"INSERT INTO recovery_records ({_COLUMNS}) "
                        f"VALUES ({','.join('?' for _ in range(20))})",
                        self._serialize(record),
                    )
                self._trim(connection)
        except sqlite3.Error as error:
            raise RecoveryRecordError(
                "Omega could not replace recovery records."
            ) from error
        finally:
            connection.close()
        return self.list_records()

    def clear(self) -> None:
        connection = self.connection_factory.connect()
        try:
            with connection:
                connection.execute("DELETE FROM recovery_records")
        finally:
            connection.close()

    def prune_inactive(self, *, before: datetime) -> int:
        cutoff = validate_utc_timestamp(before, "before").isoformat()
        connection = self.connection_factory.connect()
        try:
            with connection:
                cursor = connection.execute(
                    """
                    DELETE FROM recovery_records
                    WHERE status IN ('expired','restored','failed','cancelled')
                      AND created_at < ?
                    """,
                    (cutoff,),
                )
                return cursor.rowcount
        finally:
            connection.close()

    def _list(self, order: str) -> tuple[RecoveryRecord, ...]:
        connection = self.connection_factory.connect()
        try:
            rows = connection.execute(
                f"SELECT {_COLUMNS} FROM recovery_records ORDER BY {order}"
            ).fetchall()
        except sqlite3.Error as error:
            raise RecoveryRecordError(
                "Omega could not list recovery records."
            ) from error
        finally:
            connection.close()
        return tuple(self._deserialize(row) for row in rows)

    def _trim(self, connection: sqlite3.Connection) -> None:
        row = connection.execute("SELECT COUNT(*) FROM recovery_records").fetchone()
        if row is None or int(row[0]) <= self.maximum_records:
            return
        removable = connection.execute(
            """
            SELECT record_id FROM recovery_records
            WHERE status != 'completed'
            ORDER BY created_at ASC, record_id ASC
            """
        ).fetchall()
        excess = int(row[0]) - self.maximum_records
        if len(removable) < excess:
            raise RecoveryRecordError(
                "Recovery capacity cannot discard active undo records."
            )
        connection.executemany(
            "DELETE FROM recovery_records WHERE record_id = ?",
            [(entry[0],) for entry in removable[:excess]],
        )

    @staticmethod
    def _serialize(record: RecoveryRecord) -> tuple[object, ...]:
        if not isinstance(record, RecoveryRecord):
            raise RecoveryRecordError("record must be a RecoveryRecord.")
        item = record.item

        def encode(value: object) -> str:
            return json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )

        return (
            str(record.record_id),
            record.action_type.value,
            record.resource_type.value,
            str(record.command_id),
            str(record.action_id),
            str(record.session_id),
            item.display_name,
            item.logical_location,
            item.relative_path,
            item.original_path_fingerprint,
            item.recycle_bin_reference,
            item.size_bytes,
            item.recycled_at.isoformat(),
            encode(item.metadata),
            record.status.value,
            record.created_at.isoformat(),
            record.expires_at.isoformat() if record.expires_at else None,
            record.restored_at.isoformat() if record.restored_at else None,
            record.failure_code,
            encode(record.metadata),
        )

    @staticmethod
    def _deserialize(row: Mapping[str, Any]) -> RecoveryRecord:
        try:
            item_metadata = json.loads(str(row["item_metadata_json"]))
            metadata = json.loads(str(row["metadata_json"]))
            if not isinstance(item_metadata, dict) or not isinstance(metadata, dict):
                raise ValueError
            resource_type = RecoveryResourceType(str(row["resource_type"]))
            item = RecycleBinItem(
                resource_type=resource_type,
                display_name=str(row["display_name"]),
                logical_location=str(row["logical_location"]),
                relative_path=str(row["relative_path"]),
                original_path_fingerprint=str(row["original_path_fingerprint"]),
                recycled_at=parse_utc_timestamp(row["recycled_at"], "recycled_at"),
                recycle_bin_reference=row["recycle_bin_reference"],
                size_bytes=row["size_bytes"],
                metadata=item_metadata,
            )
            return RecoveryRecord(
                record_id=UUID(str(row["record_id"])),
                action_type=RecoverableActionType(str(row["action_type"])),
                resource_type=resource_type,
                command_id=UUID(str(row["command_id"])),
                action_id=UUID(str(row["action_id"])),
                session_id=UUID(str(row["session_id"])),
                item=item,
                status=RecoveryRecordStatus(str(row["status"])),
                created_at=parse_utc_timestamp(row["created_at"], "created_at"),
                expires_at=(
                    parse_utc_timestamp(row["expires_at"], "expires_at")
                    if row["expires_at"]
                    else None
                ),
                restored_at=(
                    parse_utc_timestamp(row["restored_at"], "restored_at")
                    if row["restored_at"]
                    else None
                ),
                failure_code=row["failure_code"],
                metadata=metadata,
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ModelValidationError,
        ) as error:
            raise RecoveryRecordError("A stored recovery record is invalid.") from error

    @staticmethod
    def _validate_id(record_id: UUID) -> None:
        if not isinstance(record_id, UUID):
            raise RecoveryRecordError("record_id must be a UUID.")
