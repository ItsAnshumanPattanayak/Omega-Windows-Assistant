"""Tests for structured recovery results."""

from datetime import datetime
from uuid import uuid4

import pytest

from omega.core.exceptions import ModelValidationError
from omega.recovery import (
    RecoverableActionType,
    RecoveryRecord,
    RecoveryRecordStatus,
    RecoveryResourceType,
    RecoveryResult,
    RecycleBinItem,
)


def make_record() -> RecoveryRecord:
    """Create a completed recoverable record."""

    item = RecycleBinItem(
        resource_type=RecoveryResourceType.FILE,
        display_name="notes.txt",
        logical_location="documents",
        relative_path="notes.txt",
        original_path_fingerprint="private-fingerprint",
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


def test_recovery_result_serializes_safe_record() -> None:
    result = RecoveryResult(
        success=True,
        code="RECYCLE_COMPLETED",
        message="The file was moved to the Recycle Bin.",
        record=make_record(),
    )

    serialized = result.to_dict()

    assert serialized["success"] is True
    assert serialized["code"] == "RECYCLE_COMPLETED"

    record = serialized["record"]
    assert isinstance(record, dict)
    assert record["status"] == "completed"

    assert "private-fingerprint" not in str(serialized)


def test_recovery_result_requires_non_empty_code() -> None:
    with pytest.raises(ModelValidationError, match="code"):
        RecoveryResult(
            success=False,
            code="",
            message="Recovery failed.",
        )


def test_recovery_result_requires_non_empty_message() -> None:
    with pytest.raises(ModelValidationError, match="message"):
        RecoveryResult(
            success=False,
            code="RECOVERY_FAILED",
            message="",
        )


def test_recovery_result_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ModelValidationError, match="timezone-aware"):
        RecoveryResult(
            success=True,
            code="RECOVERY_OK",
            message="Recovery completed.",
            completed_at=datetime.now(),
        )


def test_recovery_result_rejects_invalid_record() -> None:
    with pytest.raises(ModelValidationError, match="RecoveryRecord"):
        RecoveryResult(
            success=True,
            code="RECOVERY_OK",
            message="Recovery completed.",
            record="invalid",  # type: ignore[arg-type]
        )


def test_recovery_result_metadata_defaults_are_independent() -> None:
    first = RecoveryResult(
        success=True,
        code="FIRST",
        message="First result.",
    )
    second = RecoveryResult(
        success=True,
        code="SECOND",
        message="Second result.",
    )

    assert first.metadata == {}
    assert second.metadata == {}
    assert first.metadata is not second.metadata
