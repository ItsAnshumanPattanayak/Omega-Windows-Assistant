"""Undo-aware registry for process-local recovery records."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from uuid import UUID

from omega.core.exceptions import RecoveryRecordError
from omega.models._serialization import utc_now, validate_utc_timestamp
from omega.recovery.configuration import RecoveryConfiguration
from omega.recovery.models import (
    RecoveryRecord,
    RecoveryRecordStatus,
)
from omega.recovery.store import InMemoryRecoveryRecordStore, RecoveryRecordStore


class RecoveryRegistry:
    """Manage recovery records, expiry, and undo eligibility."""

    def __init__(
        self,
        configuration: RecoveryConfiguration,
        store: RecoveryRecordStore | None = None,
    ) -> None:
        if not isinstance(configuration, RecoveryConfiguration):
            raise TypeError("configuration must be a RecoveryConfiguration.")

        self._configuration = configuration

        selected_store: RecoveryRecordStore
        if store is None:
            selected_store = InMemoryRecoveryRecordStore(
                maximum_records=configuration.maximum_undo_records
            )
        else:
            selected_store = store
        self._store = selected_store

        if self._store.maximum_records != configuration.maximum_undo_records:
            raise RecoveryRecordError(
                "Recovery store capacity must match recovery configuration."
            )

    @property
    def store(self) -> RecoveryRecordStore:
        """Return the configured record store."""

        return self._store

    def register(
        self,
        record: RecoveryRecord,
        *,
        registered_at: datetime | None = None,
    ) -> RecoveryRecord:
        """Register one completed, restorable recovery record."""

        if not isinstance(record, RecoveryRecord):
            raise RecoveryRecordError("record must be a RecoveryRecord.")

        if record.status is not RecoveryRecordStatus.COMPLETED:
            raise RecoveryRecordError(
                "Only completed recovery records can be registered for undo."
            )

        normalized_registered_at = self._normalize_now(registered_at)

        if normalized_registered_at < record.created_at:
            raise RecoveryRecordError(
                "registered_at must not precede record.created_at."
            )

        expected_expiry = record.created_at + timedelta(
            seconds=self._configuration.undo_timeout_seconds
        )

        if record.expires_at is None:
            registered_record = replace(
                record,
                expires_at=expected_expiry,
            )
        else:
            registered_record = record

        if registered_record.expires_at is None:
            raise RecoveryRecordError("Registered recovery records require expires_at.")

        if registered_record.expires_at <= normalized_registered_at:
            registered_record = replace(
                registered_record,
                status=RecoveryRecordStatus.EXPIRED,
            )

        return self._store.add(registered_record)

    def get(
        self,
        record_id: UUID,
        *,
        now: datetime | None = None,
    ) -> RecoveryRecord | None:
        """Return a record after applying expiration rules."""

        record = self._store.get(record_id)

        if record is None:
            return None

        return self._expire_record_if_needed(
            record,
            now=self._normalize_now(now),
        )

    def require(
        self,
        record_id: UUID,
        *,
        now: datetime | None = None,
    ) -> RecoveryRecord:
        """Return a record or raise when it does not exist."""

        record = self.get(record_id, now=now)

        if record is None:
            raise RecoveryRecordError("The requested recovery record was not found.")

        return record

    def list_records(
        self,
        *,
        now: datetime | None = None,
        newest_first: bool = True,
    ) -> tuple[RecoveryRecord, ...]:
        """Return records after applying expiration rules."""

        normalized_now = self._normalize_now(now)

        if newest_first:
            records = self._store.list_newest_first()
        else:
            records = self._store.list_records()

        return tuple(
            self._expire_record_if_needed(
                record,
                now=normalized_now,
            )
            for record in records
        )

    def list_restorable(
        self,
        *,
        now: datetime | None = None,
    ) -> tuple[RecoveryRecord, ...]:
        """Return all currently restorable records, newest first."""

        records = self.list_records(
            now=now,
            newest_first=True,
        )

        return tuple(record for record in records if record.can_restore)

    def latest_restorable(
        self,
        *,
        now: datetime | None = None,
    ) -> RecoveryRecord | None:
        """Return the newest currently restorable record."""

        restorable_records = self.list_restorable(now=now)

        if not restorable_records:
            return None

        return restorable_records[0]

    def mark_restored(
        self,
        record_id: UUID,
        *,
        restored_at: datetime | None = None,
    ) -> RecoveryRecord:
        """Mark a currently restorable record as restored."""

        normalized_restored_at = self._normalize_now(restored_at)
        record = self.require(
            record_id,
            now=normalized_restored_at,
        )

        if record.status is RecoveryRecordStatus.EXPIRED:
            raise RecoveryRecordError("Expired recovery records cannot be restored.")

        if record.status is RecoveryRecordStatus.RESTORED:
            raise RecoveryRecordError("The recovery record has already been restored.")

        if record.status is not RecoveryRecordStatus.COMPLETED:
            raise RecoveryRecordError(
                "Only completed recovery records can be marked restored."
            )

        if normalized_restored_at < record.created_at:
            raise RecoveryRecordError("restored_at must not precede record.created_at.")

        updated_record = replace(
            record,
            status=RecoveryRecordStatus.RESTORED,
            restored_at=normalized_restored_at,
        )

        return self._store.update(updated_record)

    def mark_failed(
        self,
        record_id: UUID,
        *,
        failure_code: str,
        failed_at: datetime | None = None,
    ) -> RecoveryRecord:
        """Mark a recovery record as failed."""

        if not isinstance(failure_code, str) or not failure_code.strip():
            raise RecoveryRecordError("failure_code must be a non-empty string.")

        normalized_failed_at = self._normalize_now(failed_at)
        record = self.require(
            record_id,
            now=normalized_failed_at,
        )

        if record.status is RecoveryRecordStatus.RESTORED:
            raise RecoveryRecordError(
                "Restored recovery records cannot be marked failed."
            )

        updated_record = replace(
            record,
            status=RecoveryRecordStatus.FAILED,
            failure_code=failure_code.strip(),
            restored_at=None,
        )

        return self._store.update(updated_record)

    def mark_cancelled(
        self,
        record_id: UUID,
        *,
        now: datetime | None = None,
    ) -> RecoveryRecord:
        """Mark a non-restored record as cancelled."""

        normalized_now = self._normalize_now(now)
        record = self.require(record_id, now=normalized_now)

        if record.status is RecoveryRecordStatus.RESTORED:
            raise RecoveryRecordError("Restored recovery records cannot be cancelled.")

        if record.status is RecoveryRecordStatus.CANCELLED:
            return record

        updated_record = replace(
            record,
            status=RecoveryRecordStatus.CANCELLED,
            restored_at=None,
            failure_code=None,
        )

        return self._store.update(updated_record)

    def expire_records(
        self,
        *,
        now: datetime | None = None,
    ) -> tuple[RecoveryRecord, ...]:
        """Apply expiration rules and return records newly expired."""

        normalized_now = self._normalize_now(now)
        expired_records: list[RecoveryRecord] = []

        for record in self._store.list_records():
            updated_record = self._expire_record_if_needed(
                record,
                now=normalized_now,
            )

            if (
                updated_record.status is RecoveryRecordStatus.EXPIRED
                and record.status is not RecoveryRecordStatus.EXPIRED
            ):
                expired_records.append(updated_record)

        return tuple(expired_records)

    def remove(self, record_id: UUID) -> RecoveryRecord | None:
        """Remove one process-local recovery record."""

        return self._store.remove(record_id)

    def clear(self) -> None:
        """Clear all process-local recovery records."""

        self._store.clear()

    def _expire_record_if_needed(
        self,
        record: RecoveryRecord,
        *,
        now: datetime,
    ) -> RecoveryRecord:
        if record.status is not RecoveryRecordStatus.COMPLETED:
            return record

        if record.expires_at is None:
            return record

        if record.expires_at > now:
            return record

        expired_record = replace(
            record,
            status=RecoveryRecordStatus.EXPIRED,
        )

        return self._store.update(expired_record)

    @staticmethod
    def _normalize_now(value: datetime | None) -> datetime:
        if value is None:
            return utc_now()

        return validate_utc_timestamp(value, "now")
