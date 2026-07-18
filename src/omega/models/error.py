"""Serializable diagnostic records, separate from Python exception classes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from omega.core.exceptions import ModelValidationError
from omega.models._serialization import (
    JsonValue,
    parse_utc_timestamp,
    parse_uuid,
    serialize_value,
    utc_now,
    validate_json_mapping,
    validate_utc_timestamp,
)
from omega.models.enums import ErrorCategory

_SENSITIVE_DETAIL_KEYS = frozenset(
    {
        "authorization",
        "credential",
        "credentials",
        "password",
        "secret",
        "stack_trace",
        "token",
        "traceback",
    }
)


def _validate_error_code(code: str) -> str:
    if not isinstance(code, str) or not code:
        raise ModelValidationError("code must be a non-empty machine-readable string.")
    if code.startswith("_") or code.endswith("_"):
        raise ModelValidationError("code must not start or end with an underscore.")
    parts = code.split("_")
    if not all(part.isalnum() and part.upper() == part for part in parts):
        raise ModelValidationError(
            "code must use uppercase letters, numbers, and single underscores."
        )
    return code


def _reject_sensitive_detail_keys(value: Mapping[str, Any]) -> None:
    for key, item in value.items():
        normalized = key.lower()
        if normalized in _SENSITIVE_DETAIL_KEYS:
            raise ModelValidationError(
                f"details must not include sensitive field '{key}'."
            )
        if isinstance(item, Mapping):
            _reject_sensitive_detail_keys(item)


@dataclass
class OmegaErrorDetails:
    """Safe, serializable error data; this does not replace Python exceptions."""

    code: str
    category: ErrorCategory
    message: str
    user_message: str
    recoverable: bool
    details: dict[str, JsonValue] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=utc_now)
    action_id: UUID | None = None
    command_id: UUID | None = None

    def __post_init__(self) -> None:
        self.code = _validate_error_code(self.code)
        if not isinstance(self.category, ErrorCategory):
            raise ModelValidationError("category must be an ErrorCategory.")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ModelValidationError("message must be a non-empty diagnostic string.")
        if not isinstance(self.user_message, str) or not self.user_message.strip():
            raise ModelValidationError("user_message must be a non-empty safe string.")
        if not isinstance(self.recoverable, bool):
            raise ModelValidationError("recoverable must be a boolean.")
        if self.action_id is not None and not isinstance(self.action_id, UUID):
            raise ModelValidationError("action_id must be a UUID or None.")
        if self.command_id is not None and not isinstance(self.command_id, UUID):
            raise ModelValidationError("command_id must be a UUID or None.")
        _reject_sensitive_detail_keys(self.details)
        self.details = validate_json_mapping(self.details, "details")
        self.occurred_at = validate_utc_timestamp(self.occurred_at, "occurred_at")

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize error data without introducing diagnostic-only private data."""
        return {
            "code": self.code,
            "category": self.category.value,
            "message": self.message,
            "user_message": self.user_message,
            "recoverable": self.recoverable,
            "details": self.details,
            "occurred_at": serialize_value(self.occurred_at),
            "action_id": str(self.action_id) if self.action_id else None,
            "command_id": str(self.command_id) if self.command_id else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OmegaErrorDetails:
        """Deserialize a previously serialized error record."""
        try:
            action_id = data.get("action_id")
            command_id = data.get("command_id")
            return cls(
                code=data["code"],
                category=ErrorCategory(data["category"]),
                message=data["message"],
                user_message=data["user_message"],
                recoverable=data["recoverable"],
                details=data.get("details", {}),
                occurred_at=parse_utc_timestamp(data["occurred_at"], "occurred_at"),
                action_id=parse_uuid(action_id, "action_id") if action_id else None,
                command_id=parse_uuid(command_id, "command_id") if command_id else None,
            )
        except KeyError as error:
            raise ModelValidationError(
                f"Missing error field: {error.args[0]}."
            ) from error
