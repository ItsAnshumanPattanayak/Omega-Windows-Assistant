"""Typed entities extracted by a future command-understanding layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from omega.core.exceptions import ModelValidationError
from omega.models._serialization import (
    JsonValue,
    validate_json_mapping,
    validate_json_value,
)
from omega.models.enums import EntityType


def _validate_confidence(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelValidationError(
            f"{field_name} must be a number between 0.0 and 1.0."
        )
    confidence = float(value)
    if not 0.0 <= confidence <= 1.0:
        raise ModelValidationError(f"{field_name} must be between 0.0 and 1.0.")
    return confidence


def _validate_index(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ModelValidationError(
            f"{field_name} must be a non-negative integer when supplied."
        )
    return value


@dataclass
class CommandEntity:
    """One future-extracted, JSON-compatible value from a user command.

    Entities are data records only; Phase 1 deliberately does not extract them.
    Callers should treat instances as immutable after construction.
    """

    entity_type: EntityType
    value: JsonValue
    raw_value: str | None = None
    name: str | None = None
    confidence: float = 1.0
    start_index: int | None = None
    end_index: int | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.value = validate_json_value(self.value, "value")
        self.metadata = validate_json_mapping(self.metadata, "metadata")
        self.confidence = _validate_confidence(self.confidence, "confidence")
        self.start_index = _validate_index(self.start_index, "start_index")
        self.end_index = _validate_index(self.end_index, "end_index")
        if self.start_index is not None and self.end_index is not None:
            if self.end_index < self.start_index:
                raise ModelValidationError(
                    "end_index must not be less than start_index."
                )
        if self.raw_value is not None and not isinstance(self.raw_value, str):
            raise ModelValidationError("raw_value must be a string or None.")
        if self.name is not None:
            if not isinstance(self.name, str) or not self.name.strip():
                raise ModelValidationError("name must be a non-empty string or None.")

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize this entity using stable enum values."""
        return {
            "entity_type": self.entity_type.value,
            "value": self.value,
            "raw_value": self.raw_value,
            "name": self.name,
            "confidence": self.confidence,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CommandEntity:
        """Deserialize a previously serialized entity."""
        try:
            return cls(
                entity_type=EntityType(data["entity_type"]),
                value=data["value"],
                raw_value=data.get("raw_value"),
                name=data.get("name"),
                confidence=data.get("confidence", 1.0),
                start_index=data.get("start_index"),
                end_index=data.get("end_index"),
                metadata=data.get("metadata", {}),
            )
        except KeyError as error:
            raise ModelValidationError(
                f"Missing entity field: {error.args[0]}."
            ) from error
