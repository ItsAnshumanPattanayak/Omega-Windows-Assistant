from pathlib import Path

import pytest

from omega.core.exceptions import ModelValidationError
from omega.models import Action, IntentType, UserCommand


def test_context_is_typed_deterministic_and_redacts_paths(
    context_factory, tmp_path: Path
):
    source = tmp_path / "private" / "notes.txt"
    context = context_factory(
        source_path=source,
        logical_source="Desktop/notes.txt",
        additional_context={"target_has_content": True},
    )

    serialized = context.to_dict()

    assert serialized["logical_source"] == "Desktop/notes.txt"
    assert str(source) not in str(serialized)
    assert context.requested_at.utcoffset() is not None


def test_context_rejects_mismatched_command_and_action_ids():
    command = UserCommand("Read notes.txt", intent=IntentType.READ_FILE)
    other = UserCommand("Read other.txt", intent=IntentType.READ_FILE)

    with pytest.raises(ModelValidationError, match="IDs must match"):
        from omega.safety import SafetyContext

        SafetyContext(command, Action(other.command_id, IntentType.READ_FILE))


def test_context_mutable_defaults_are_independent(context_factory):
    first = context_factory()
    second = context_factory()
    first.additional_context["safe"] = True
    assert second.additional_context == {}
