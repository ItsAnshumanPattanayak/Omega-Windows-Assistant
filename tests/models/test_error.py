"""Tests for safe serializable error records."""

import pytest

from omega.core.exceptions import ModelValidationError
from omega.models import ErrorCategory, OmegaErrorDetails


def test_error_record_serializes_and_round_trips() -> None:
    error = OmegaErrorDetails(
        "APPLICATION_NOT_FOUND",
        ErrorCategory.NOT_FOUND,
        "Alias missing",
        "I could not find that application.",
        True,
    )
    assert error.occurred_at.tzinfo is not None
    assert OmegaErrorDetails.from_dict(error.to_dict()).to_dict() == error.to_dict()


def test_error_rejects_unstable_codes_and_sensitive_details() -> None:
    with pytest.raises(ModelValidationError):
        OmegaErrorDetails("not-found", ErrorCategory.NOT_FOUND, "x", "x", True)
    with pytest.raises(ModelValidationError, match="sensitive"):
        OmegaErrorDetails(
            "SAFE_ERROR",
            ErrorCategory.INTERNAL,
            "x",
            "x",
            False,
            details={"token": "hidden"},
        )


def test_error_details_defaults_are_independent() -> None:
    first = OmegaErrorDetails("ONE", ErrorCategory.INTERNAL, "x", "x", False)
    second = OmegaErrorDetails("TWO", ErrorCategory.INTERNAL, "x", "x", False)
    first.details["context"] = "test"
    assert second.details == {}
