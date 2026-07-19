"""Tests for typed recovery models."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from omega.core.exceptions import ModelValidationError
from omega.recovery import (
    RecoverableActionType,
    RecoveryRecord,
    RecoveryRecordStatus,
    RecoveryResourceType,
    RecycleBinItem,
)


def make_item(
    resource_type: RecoveryResourceType = RecoveryResourceType.FILE,
) -> RecycleBinItem:
    """Create a safe test Recycle Bin item."""

    return RecycleBinItem(
        resource_type=resource_type,
        display_name="notes.txt",
        logical_location="documents",
        relative_path="College/notes.txt",
        original_path_fingerprint="private-path-fingerprint",
        size_bytes=12,
    )


def test_recycle_bin_item_serialization_omits_private_identifiers() -> None:
    item = make_item()

    serialized = item.to_dict()

    assert serialized["resource_type"] == "file"
    assert serialized["logical_location"] == "documents"
    assert serialized["relative_path"] == "College/notes.txt"
    assert "original_path_fingerprint" not in serialized
    assert "recycle_bin_reference" not in serialized
    assert "private-path-fingerprint" not in str(serialized)


def test_recovery_record_is_typed_and_serializable() -> None:
    now = datetime.now(UTC)
    item = make_item()

    record = RecoveryRecord(
        action_type=RecoverableActionType.RECYCLE_FILE,
        resource_type=RecoveryResourceType.FILE,
        command_id=uuid4(),
        action_id=uuid4(),
        session_id=uuid4(),
        item=item,
        status=RecoveryRecordStatus.COMPLETED,
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )

    serialized = record.to_dict()

    assert serialized["action_type"] == "recycle_file"
    assert serialized["status"] == "completed"
    assert serialized["can_restore"] is True
    assert str(serialized["created_at"]).endswith("+00:00")


def test_resource_type_mismatch_is_rejected() -> None:
    with pytest.raises(ModelValidationError, match="resource types"):
        RecoveryRecord(
            action_type=RecoverableActionType.RECYCLE_FOLDER,
            resource_type=RecoveryResourceType.FOLDER,
            command_id=uuid4(),
            action_id=uuid4(),
            session_id=uuid4(),
            item=make_item(RecoveryResourceType.FILE),
        )


def test_restored_record_requires_restored_timestamp() -> None:
    with pytest.raises(ModelValidationError, match="restored_at"):
        RecoveryRecord(
            action_type=RecoverableActionType.RESTORE_FILE,
            resource_type=RecoveryResourceType.FILE,
            command_id=uuid4(),
            action_id=uuid4(),
            session_id=uuid4(),
            item=make_item(),
            status=RecoveryRecordStatus.RESTORED,
        )


def test_failed_record_requires_failure_code() -> None:
    with pytest.raises(ModelValidationError, match="failure_code"):
        RecoveryRecord(
            action_type=RecoverableActionType.RECYCLE_FILE,
            resource_type=RecoveryResourceType.FILE,
            command_id=uuid4(),
            action_id=uuid4(),
            session_id=uuid4(),
            item=make_item(),
            status=RecoveryRecordStatus.FAILED,
        )


def test_expiry_must_follow_creation() -> None:
    now = datetime.now(UTC)

    with pytest.raises(ModelValidationError, match="expires_at"):
        RecoveryRecord(
            action_type=RecoverableActionType.RECYCLE_FILE,
            resource_type=RecoveryResourceType.FILE,
            command_id=uuid4(),
            action_id=uuid4(),
            session_id=uuid4(),
            item=make_item(),
            created_at=now,
            expires_at=now - timedelta(seconds=1),
        )


def test_invalid_size_is_rejected() -> None:
    with pytest.raises(ModelValidationError, match="size_bytes"):
        RecycleBinItem(
            resource_type=RecoveryResourceType.FILE,
            display_name="notes.txt",
            logical_location="documents",
            relative_path="notes.txt",
            original_path_fingerprint="fingerprint",
            size_bytes=-1,
        )


def test_metadata_defaults_are_independent() -> None:
    first = make_item()
    second = make_item()

    assert first.metadata == {}
    assert second.metadata == {}
    assert first.metadata is not second.metadata
