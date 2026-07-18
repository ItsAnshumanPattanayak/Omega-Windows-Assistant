"""Internal JSON-compatible value validation and conversion helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeAlias
from uuid import UUID

from omega.core.exceptions import ModelValidationError

JsonPrimitive: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def validate_utc_timestamp(value: datetime, field_name: str) -> datetime:
    """Ensure a timestamp is timezone-aware and normalized to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ModelValidationError(f"{field_name} must be timezone-aware.")
    return value.astimezone(UTC)


def parse_utc_timestamp(value: str, field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp and validate its timezone information."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ModelValidationError(
            f"{field_name} must be an ISO-8601 timestamp."
        ) from error
    return validate_utc_timestamp(parsed, field_name)


def validate_json_value(value: Any, field_name: str) -> JsonValue:
    """Validate and copy a value that can be represented by JSON."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ModelValidationError(
                f"{field_name} must not contain non-finite floats."
            )
        return value
    if isinstance(value, list):
        return [validate_json_value(item, field_name) for item in value]
    if isinstance(value, Mapping):
        copied: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ModelValidationError(f"{field_name} keys must be strings.")
            copied[key] = validate_json_value(item, field_name)
        return copied
    raise ModelValidationError(f"{field_name} must contain JSON-compatible values.")


def validate_json_mapping(
    value: Mapping[str, Any], field_name: str
) -> dict[str, JsonValue]:
    """Validate a JSON-compatible object value."""
    copied = validate_json_value(value, field_name)
    if not isinstance(copied, dict):
        raise ModelValidationError(f"{field_name} must be a JSON object.")
    return copied


def serialize_value(value: Any) -> JsonValue:
    """Convert supported model values to recursively JSON-compatible data."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        return validate_json_value(value, "serialized value")
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return validate_utc_timestamp(value, "timestamp").isoformat()
    if isinstance(value, list | tuple):
        return [serialize_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): serialize_value(item) for key, item in value.items()}
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        serialized = to_dict()
        return validate_json_value(serialized, "serialized model")
    raise ModelValidationError("Cannot serialize an unsupported value.")


def parse_uuid(value: str, field_name: str) -> UUID:
    """Parse a UUID string into a UUID value."""
    try:
        return UUID(value)
    except (TypeError, ValueError) as error:
        raise ModelValidationError(f"{field_name} must be a valid UUID.") from error
