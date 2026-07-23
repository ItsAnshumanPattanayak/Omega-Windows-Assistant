"""Process-local storage for bounded Omega recovery records."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from threading import RLock
from typing import Protocol
from uuid import UUID

from omega.core.exceptions import RecoveryRecordError
from omega.recovery.models import RecoveryRecord


class RecoveryRecordStore(Protocol):
    """Storage contract shared by in-memory and SQLite recovery stores."""

    @property
    def maximum_records(self) -> int: ...

    def add(self, record: RecoveryRecord) -> RecoveryRecord: ...

    def get(self, record_id: UUID) -> RecoveryRecord | None: ...

    def require(self, record_id: UUID) -> RecoveryRecord: ...

    def update(self, record: RecoveryRecord) -> RecoveryRecord: ...

    def remove(self, record_id: UUID) -> RecoveryRecord | None: ...

    def list_records(self) -> tuple[RecoveryRecord, ...]: ...

    def list_newest_first(self) -> tuple[RecoveryRecord, ...]: ...

    def replace_all(
        self, records: Iterable[RecoveryRecord]
    ) -> tuple[RecoveryRecord, ...]: ...

    def clear(self) -> None: ...


class InMemoryRecoveryRecordStore:
    """Thread-safe, bounded, process-local recovery record storage."""

    def __init__(self, maximum_records: int) -> None:
        if (
            isinstance(maximum_records, bool)
            or not isinstance(maximum_records, int)
            or maximum_records <= 0
        ):
            raise RecoveryRecordError("maximum_records must be a positive integer.")

        self._maximum_records = maximum_records
        self._records: OrderedDict[UUID, RecoveryRecord] = OrderedDict()
        self._lock = RLock()

    @property
    def maximum_records(self) -> int:
        """Return the configured maximum number of stored records."""

        return self._maximum_records

    def __len__(self) -> int:
        """Return the number of currently stored records."""

        with self._lock:
            return len(self._records)

    def add(self, record: RecoveryRecord) -> RecoveryRecord:
        """Add or replace a record and enforce the configured capacity."""

        if not isinstance(record, RecoveryRecord):
            raise RecoveryRecordError("record must be a RecoveryRecord.")

        with self._lock:
            self._records.pop(record.record_id, None)
            self._records[record.record_id] = record
            self._trim_to_capacity()

        return record

    def get(self, record_id: UUID) -> RecoveryRecord | None:
        """Return a stored record by identifier."""

        self._validate_record_id(record_id)

        with self._lock:
            return self._records.get(record_id)

    def require(self, record_id: UUID) -> RecoveryRecord:
        """Return a stored record or raise when it does not exist."""

        record = self.get(record_id)

        if record is None:
            raise RecoveryRecordError("The requested recovery record was not found.")

        return record

    def update(self, record: RecoveryRecord) -> RecoveryRecord:
        """Replace an existing stored record."""

        if not isinstance(record, RecoveryRecord):
            raise RecoveryRecordError("record must be a RecoveryRecord.")

        with self._lock:
            if record.record_id not in self._records:
                raise RecoveryRecordError("Cannot update an unknown recovery record.")

            self._records[record.record_id] = record

        return record

    def remove(self, record_id: UUID) -> RecoveryRecord | None:
        """Remove and return a record when present."""

        self._validate_record_id(record_id)

        with self._lock:
            return self._records.pop(record_id, None)

    def list_records(self) -> tuple[RecoveryRecord, ...]:
        """Return records in oldest-to-newest insertion order."""

        with self._lock:
            return tuple(self._records.values())

    def list_newest_first(self) -> tuple[RecoveryRecord, ...]:
        """Return records in newest-to-oldest insertion order."""

        with self._lock:
            return tuple(reversed(self._records.values()))

    def replace_all(
        self,
        records: Iterable[RecoveryRecord],
    ) -> tuple[RecoveryRecord, ...]:
        """Replace all records while enforcing capacity."""

        validated_records: list[RecoveryRecord] = []

        for record in records:
            if not isinstance(record, RecoveryRecord):
                raise RecoveryRecordError(
                    "All supplied records must be RecoveryRecord instances."
                )

            validated_records.append(record)

        with self._lock:
            self._records.clear()

            for record in validated_records:
                self._records[record.record_id] = record

            self._trim_to_capacity()

            return tuple(self._records.values())

    def clear(self) -> None:
        """Remove all process-local recovery records."""

        with self._lock:
            self._records.clear()

    def _trim_to_capacity(self) -> None:
        while len(self._records) > self._maximum_records:
            self._records.popitem(last=False)

    @staticmethod
    def _validate_record_id(record_id: UUID) -> None:
        if not isinstance(record_id, UUID):
            raise RecoveryRecordError("record_id must be a UUID.")
