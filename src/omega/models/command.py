"""Typed command records independent of command parsing or execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

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
from omega.models.entity import CommandEntity, _validate_confidence
from omega.models.enums import CommandSource, IntentType


@dataclass
class UserCommand:
    """A received command record before future normalization or intent detection.

    The original text is preserved verbatim. Instances are data-only and should be
    treated as immutable by later layers.
    """

    original_text: str
    command_id: UUID = field(default_factory=uuid4)
    normalized_text: str | None = None
    intent: IntentType = IntentType.UNKNOWN
    entities: list[CommandEntity] = field(default_factory=list)
    confidence: float = 0.0
    received_at: datetime = field(default_factory=utc_now)
    source: CommandSource = CommandSource.TEXT
    session_id: UUID | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.original_text, str) or not self.original_text.strip():
            raise ModelValidationError(
                "original_text must not be empty or whitespace-only."
            )
        if self.normalized_text is not None:
            if (
                not isinstance(self.normalized_text, str)
                or not self.normalized_text.strip()
            ):
                raise ModelValidationError(
                    "normalized_text must be a non-empty string or None."
                )
        if not isinstance(self.command_id, UUID):
            raise ModelValidationError("command_id must be a UUID.")
        if self.session_id is not None and not isinstance(self.session_id, UUID):
            raise ModelValidationError("session_id must be a UUID or None.")
        if not isinstance(self.intent, IntentType):
            raise ModelValidationError("intent must be an IntentType.")
        if not isinstance(self.source, CommandSource):
            raise ModelValidationError("source must be a CommandSource.")
        if not all(isinstance(entity, CommandEntity) for entity in self.entities):
            raise ModelValidationError("entities must contain CommandEntity values.")
        self.entities = list(self.entities)
        self.confidence = _validate_confidence(self.confidence, "confidence")
        self.received_at = validate_utc_timestamp(self.received_at, "received_at")
        self.metadata = validate_json_mapping(self.metadata, "metadata")

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize the command into JSON-compatible primitives and objects."""
        return {
            "command_id": str(self.command_id),
            "original_text": self.original_text,
            "normalized_text": self.normalized_text,
            "intent": self.intent.value,
            "entities": [entity.to_dict() for entity in self.entities],
            "confidence": self.confidence,
            "received_at": serialize_value(self.received_at),
            "source": self.source.value,
            "session_id": str(self.session_id) if self.session_id else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserCommand:
        """Deserialize a previously serialized command."""
        try:
            entity_data = data.get("entities", [])
            if not isinstance(entity_data, list):
                raise ModelValidationError("entities must be a list.")
            session_id = data.get("session_id")
            return cls(
                original_text=data["original_text"],
                command_id=parse_uuid(data["command_id"], "command_id"),
                normalized_text=data.get("normalized_text"),
                intent=IntentType(data.get("intent", IntentType.UNKNOWN.value)),
                entities=[CommandEntity.from_dict(entity) for entity in entity_data],
                confidence=data.get("confidence", 0.0),
                received_at=parse_utc_timestamp(data["received_at"], "received_at"),
                source=CommandSource(data.get("source", CommandSource.TEXT.value)),
                session_id=parse_uuid(session_id, "session_id") if session_id else None,
                metadata=data.get("metadata", {}),
            )
        except KeyError as error:
            raise ModelValidationError(
                f"Missing command field: {error.args[0]}."
            ) from error
