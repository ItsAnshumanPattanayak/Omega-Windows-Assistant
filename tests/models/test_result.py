"""Tests for typed action outcome records."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from omega.core.exceptions import ModelValidationError
from omega.models import ActionResult, ActionStatus, ErrorCategory, OmegaErrorDetails


def _error() -> OmegaErrorDetails:
    return OmegaErrorDetails(
        "OPERATION_FAILED",
        ErrorCategory.EXECUTION,
        "Failure",
        "The operation failed.",
        True,
    )


def test_result_factories_and_nested_round_trip() -> None:
    success = ActionResult.success_result(uuid4(), "Done", "Done", data={"count": 1})
    failure = ActionResult.failure_result(uuid4(), "Failed", "Failed", _error())
    assert success.error is None
    assert failure.error is not None
    assert ActionResult.from_dict(failure.to_dict()).to_dict() == failure.to_dict()


def test_result_validates_error_status_duration_and_time() -> None:
    with pytest.raises(ModelValidationError):
        ActionResult(
            uuid4(), True, ActionStatus.SUCCEEDED, "Done", "Done", error=_error()
        )
    with pytest.raises(ModelValidationError):
        ActionResult(uuid4(), False, ActionStatus.FAILED, "Failed", "Failed")
    with pytest.raises(ModelValidationError):
        ActionResult(
            uuid4(), True, ActionStatus.SUCCEEDED, "Done", "Done", duration_ms=-1
        )
    now = datetime.now(UTC)
    with pytest.raises(ModelValidationError):
        ActionResult(
            uuid4(),
            True,
            ActionStatus.SUCCEEDED,
            "Done",
            "Done",
            started_at=now,
            completed_at=now - timedelta(seconds=1),
        )


def test_result_data_and_metadata_defaults_are_independent() -> None:
    first = ActionResult(uuid4(), True, ActionStatus.SUCCEEDED, "Done", "Done")
    second = ActionResult(uuid4(), True, ActionStatus.SUCCEEDED, "Done", "Done")
    assert isinstance(first.data, dict)
    first.data["value"] = "one"
    first.metadata["value"] = "one"
    assert second.data == {}
    assert second.metadata == {}
