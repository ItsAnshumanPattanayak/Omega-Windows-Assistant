"""Tests for received command records."""

from datetime import UTC

import pytest

from omega.core.exceptions import ModelValidationError
from omega.models import CommandEntity, EntityType, IntentType, UserCommand


def test_command_defaults_preserve_text_and_round_trip() -> None:
    command = UserCommand("  Open Chrome  ")
    assert command.original_text == "  Open Chrome  "
    assert command.intent is IntentType.UNKNOWN
    assert command.command_id
    assert command.received_at.tzinfo is UTC
    assert UserCommand.from_dict(command.to_dict()).to_dict() == command.to_dict()


@pytest.mark.parametrize("text", ["", "   "])
def test_command_rejects_empty_text(text: str) -> None:
    with pytest.raises(ModelValidationError):
        UserCommand(text)


def test_command_validates_confidence_and_independent_defaults() -> None:
    with pytest.raises(ModelValidationError):
        UserCommand("Help", confidence=1.1)
    first = UserCommand("Help")
    second = UserCommand("Help")
    first.entities.append(CommandEntity(EntityType.TEXT_CONTENT, "help"))
    first.metadata["origin"] = "test"
    assert second.entities == []
    assert second.metadata == {}
