"""Tests for process-local recovery record storage."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from omega.core.exceptions import RecoveryRecordError
from omega.recovery.models import (
    RecoverableActionType,
    RecoveryRecord,
    RecoveryRecordStatus,
    RecoveryResourceType,
    RecycleBinItem,
)
from omega.recovery.store import InMemoryRecoveryRecordStore


def _record() -> RecoveryRecord:
    item = RecycleBinItem(
        resource_type=RecoveryResourceType.FILE,
        display_name="notes.txt",
        logical_location="desktop",
        relative_path="notes.txt",
        original_path_fingerprint="a" * 64,
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
        status=RecoveryRecordStatus.COMPLETED,
    )


@pytest.mark.parametrize(
    "maximum_records",
    [
        0,
        -1,
        True,
        1.5,
    ],
)
def test_invalid_capacity_is_rejected(
    maximum_records: object,
) -> None:
    with pytest.raises(RecoveryRecordError):
        InMemoryRecoveryRecordStore(maximum_records)  # type: ignore[arg-type]


def test_add_and_get_record() -> None:
    store = InMemoryRecoveryRecordStore(maximum_records=3)
    record = _record()

    added = store.add(record)

    assert added == record
    assert store.get(record.record_id) == record
    assert len(store) == 1


def test_require_unknown_record_raises() -> None:
    store = InMemoryRecoveryRecordStore(maximum_records=3)

    with pytest.raises(
        RecoveryRecordError,
        match="not found",
    ):
        store.require(uuid4())


def test_capacity_removes_oldest_record() -> None:
    store = InMemoryRecoveryRecordStore(maximum_records=2)

    first = _record()
    second = _record()
    third = _record()

    store.add(first)
    store.add(second)
    store.add(third)

    assert store.get(first.record_id) is None
    assert store.get(second.record_id) == second
    assert store.get(third.record_id) == third
    assert len(store) == 2


def test_readding_record_moves_it_to_newest_position() -> None:
    store = InMemoryRecoveryRecordStore(maximum_records=2)

    first = _record()
    second = _record()

    store.add(first)
    store.add(second)
    store.add(first)

    assert store.list_newest_first() == (first, second)


def test_update_existing_record() -> None:
    store = InMemoryRecoveryRecordStore(maximum_records=3)
    record = _record()
    store.add(record)

    updated = RecoveryRecord(
        action_type=record.action_type,
        resource_type=record.resource_type,
        command_id=record.command_id,
        action_id=record.action_id,
        session_id=record.session_id,
        item=record.item,
        status=RecoveryRecordStatus.CANCELLED,
        record_id=record.record_id,
        created_at=record.created_at,
    )

    result = store.update(updated)

    assert result.status is RecoveryRecordStatus.CANCELLED
    assert store.require(record.record_id) == updated


def test_updating_unknown_record_raises() -> None:
    store = InMemoryRecoveryRecordStore(maximum_records=3)

    with pytest.raises(
        RecoveryRecordError,
        match="unknown",
    ):
        store.update(_record())


def test_remove_returns_removed_record() -> None:
    store = InMemoryRecoveryRecordStore(maximum_records=3)
    record = _record()
    store.add(record)

    removed = store.remove(record.record_id)

    assert removed == record
    assert store.get(record.record_id) is None


def test_clear_removes_all_records() -> None:
    store = InMemoryRecoveryRecordStore(maximum_records=3)

    store.add(_record())
    store.add(_record())

    store.clear()

    assert len(store) == 0
    assert store.list_records() == ()


def test_invalid_record_identifier_is_rejected() -> None:
    store = InMemoryRecoveryRecordStore(maximum_records=3)

    with pytest.raises(
        RecoveryRecordError,
        match="UUID",
    ):
        store.get("invalid")  # type: ignore[arg-type]


def test_replace_all_enforces_capacity() -> None:
    store = InMemoryRecoveryRecordStore(maximum_records=2)

    first = _record()
    second = _record()
    third = _record()

    result = store.replace_all((first, second, third))

    assert result == (second, third)
    assert store.list_records() == (second, third)


def test_record_id_is_uuid() -> None:
    record = _record()

    assert isinstance(record.record_id, UUID)
