"""Tests for the recovery undo registry."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest

from omega.core.exceptions import RecoveryRecordError
from omega.models._serialization import utc_now
from omega.recovery.configuration import RecoveryConfiguration
from omega.recovery.models import (
    RecoverableActionType,
    RecoveryRecord,
    RecoveryRecordStatus,
    RecoveryResourceType,
    RecycleBinItem,
)
from omega.recovery.registry import RecoveryRegistry
from omega.recovery.store import InMemoryRecoveryRecordStore


def _record(
    *,
    status: RecoveryRecordStatus = RecoveryRecordStatus.COMPLETED,
) -> RecoveryRecord:
    item = RecycleBinItem(
        resource_type=RecoveryResourceType.FILE,
        display_name="notes.txt",
        logical_location="desktop",
        relative_path="notes.txt",
        original_path_fingerprint="b" * 64,
        recycle_bin_reference="test-reference",
        size_bytes=10,
    )

    return RecoveryRecord(
        action_type=RecoverableActionType.RECYCLE_FILE,
        resource_type=RecoveryResourceType.FILE,
        command_id=uuid4(),
        action_id=uuid4(),
        session_id=uuid4(),
        item=item,
        status=status,
    )


def _registry(
    *,
    timeout_seconds: int = 300,
    maximum_records: int = 20,
) -> RecoveryRegistry:
    configuration = RecoveryConfiguration(
        undo_timeout_seconds=timeout_seconds,
        maximum_undo_records=maximum_records,
    )

    return RecoveryRegistry(configuration)


def test_register_assigns_expiration_time() -> None:
    registry = _registry(timeout_seconds=120)
    record = _record()

    registered = registry.register(
        record,
        registered_at=record.created_at,
    )

    assert registered.expires_at == (record.created_at + timedelta(seconds=120))
    assert registered.can_restore is True


def test_non_completed_record_cannot_be_registered() -> None:
    registry = _registry()
    record = _record(status=RecoveryRecordStatus.CANCELLED)

    with pytest.raises(
        RecoveryRecordError,
        match="Only completed",
    ):
        registry.register(record)


def test_expired_record_is_marked_expired_during_registration() -> None:
    registry = _registry(timeout_seconds=10)
    record = _record()

    registered = registry.register(
        record,
        registered_at=record.created_at + timedelta(seconds=11),
    )

    assert registered.status is RecoveryRecordStatus.EXPIRED
    assert registered.can_restore is False


def test_latest_restorable_returns_newest_record() -> None:
    registry = _registry()

    first = _record()
    second = _record()

    registry.register(first, registered_at=first.created_at)
    registry.register(second, registered_at=second.created_at)

    latest = registry.latest_restorable(
        now=max(first.created_at, second.created_at),
    )

    assert latest is not None
    assert latest.record_id == second.record_id


def test_expired_records_are_excluded_from_restorable_list() -> None:
    registry = _registry(timeout_seconds=10)
    record = _record()

    registry.register(record, registered_at=record.created_at)

    restorable = registry.list_restorable(
        now=record.created_at + timedelta(seconds=11),
    )

    assert restorable == ()

    stored = registry.require(
        record.record_id,
        now=record.created_at + timedelta(seconds=11),
    )

    assert stored.status is RecoveryRecordStatus.EXPIRED


def test_mark_restored_updates_record_state() -> None:
    registry = _registry()
    record = _record()

    registered = registry.register(
        record,
        registered_at=record.created_at,
    )
    restored_at = registered.created_at + timedelta(seconds=1)

    restored = registry.mark_restored(
        registered.record_id,
        restored_at=restored_at,
    )

    assert restored.status is RecoveryRecordStatus.RESTORED
    assert restored.restored_at == restored_at
    assert restored.can_restore is False


def test_expired_record_cannot_be_marked_restored() -> None:
    registry = _registry(timeout_seconds=10)
    record = _record()

    registered = registry.register(
        record,
        registered_at=record.created_at,
    )

    with pytest.raises(
        RecoveryRecordError,
        match="Expired",
    ):
        registry.mark_restored(
            registered.record_id,
            restored_at=record.created_at + timedelta(seconds=11),
        )


def test_mark_failed_sets_failure_code() -> None:
    registry = _registry()
    record = _record()

    registered = registry.register(
        record,
        registered_at=record.created_at,
    )

    failed = registry.mark_failed(
        registered.record_id,
        failure_code="restore_failed",
        failed_at=registered.created_at,
    )

    assert failed.status is RecoveryRecordStatus.FAILED
    assert failed.failure_code == "restore_failed"
    assert failed.can_restore is False


def test_blank_failure_code_is_rejected() -> None:
    registry = _registry()
    record = _record()

    registered = registry.register(
        record,
        registered_at=record.created_at,
    )

    with pytest.raises(
        RecoveryRecordError,
        match="non-empty",
    ):
        registry.mark_failed(
            registered.record_id,
            failure_code=" ",
        )


def test_mark_cancelled_updates_record() -> None:
    registry = _registry()
    record = _record()

    registered = registry.register(
        record,
        registered_at=record.created_at,
    )

    cancelled = registry.mark_cancelled(
        registered.record_id,
        now=registered.created_at,
    )

    assert cancelled.status is RecoveryRecordStatus.CANCELLED
    assert cancelled.can_restore is False


def test_expire_records_returns_newly_expired_records() -> None:
    registry = _registry(timeout_seconds=10)
    record = _record()

    registered = registry.register(
        record,
        registered_at=record.created_at,
    )

    expired = registry.expire_records(
        now=record.created_at + timedelta(seconds=11),
    )

    assert len(expired) == 1
    assert expired[0].record_id == registered.record_id
    assert expired[0].status is RecoveryRecordStatus.EXPIRED

    expired_again = registry.expire_records(
        now=record.created_at + timedelta(seconds=12),
    )

    assert expired_again == ()


def test_registry_enforces_configured_capacity() -> None:
    registry = _registry(maximum_records=2)

    first = _record()
    second = _record()
    third = _record()

    registry.register(first, registered_at=first.created_at)
    registry.register(second, registered_at=second.created_at)
    registry.register(third, registered_at=third.created_at)

    records = registry.list_records(
        now=max(
            first.created_at,
            second.created_at,
            third.created_at,
        )
    )

    assert len(records) == 2
    assert registry.get(first.record_id) is None


def test_store_capacity_must_match_configuration() -> None:
    configuration = RecoveryConfiguration(maximum_undo_records=3)
    store = InMemoryRecoveryRecordStore(maximum_records=2)

    with pytest.raises(
        RecoveryRecordError,
        match="capacity",
    ):
        RecoveryRegistry(
            configuration=configuration,
            store=store,
        )


def test_registration_time_cannot_precede_creation() -> None:
    registry = _registry()
    record = _record()

    with pytest.raises(
        RecoveryRecordError,
        match="must not precede",
    ):
        registry.register(
            record,
            registered_at=record.created_at - timedelta(seconds=1),
        )


def test_existing_expiration_time_is_preserved() -> None:
    registry = _registry(timeout_seconds=300)
    record = _record()
    custom_expiry = record.created_at + timedelta(seconds=30)
    record_with_expiry = replace(
        record,
        expires_at=custom_expiry,
    )

    registered = registry.register(
        record_with_expiry,
        registered_at=record.created_at,
    )

    assert registered.expires_at == custom_expiry


def test_default_time_is_utc_aware() -> None:
    current_time = utc_now()

    assert current_time.tzinfo is not None
    assert current_time.utcoffset() == timedelta(0)
