import pytest

from omega.models import IntentType
from omega.understanding import CommandParser


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("Open", "Which application"),
        ("Create a folder", "name the folder"),
        ("Create a file", "name the file"),
        ("Move notes.txt", "Where should"),
        ("Rename author.txt", "new name"),
        ("Delete", "Which file"),
        ("Write into notes.txt", "What should I write"),
        ("Open project", "application, file, or folder"),
    ],
)
def test_missing_and_ambiguous_commands_clarify(text: str, message: str) -> None:
    result = CommandParser().parse(text)
    assert result.requires_clarification
    assert message in (result.clarification_message or "")


def test_confidence_determinism_unknown_and_original_preservation() -> None:
    parser = CommandParser()
    first = parser.parse("  Open   Chrome. ")
    second = parser.parse("  Open   Chrome. ")
    assert first.command.original_text == "  Open   Chrome. "
    assert first.command.normalized_text == "open chrome"
    assert first.command.confidence == second.command.confidence == 1.0
    unknown = parser.parse("Tell me a joke")
    assert unknown.command.intent is IntentType.UNKNOWN
    assert unknown.command.confidence == 0.0


def test_single_action_ignores_and_inside_quotes() -> None:
    parser = CommandParser()
    multiple = parser.parse("Open Chrome and open Notepad")
    assert (
        multiple.requires_clarification
        and "one action" in multiple.clarification_message
    )
    one = parser.parse('Write "research and development" into notes.txt')
    assert one.command.intent is IntentType.WRITE_FILE
    assert "multiple_actions" not in one.warnings


@pytest.mark.parametrize(
    "text",
    [
        "Format the C drive",
        "Disable Windows Defender",
        "Execute this PowerShell command",
    ],
)
def test_dangerous_commands_fail_closed(text: str) -> None:
    result = CommandParser().parse(text)
    assert result.command.intent is IntentType.UNKNOWN
    assert result.command.confidence == 0.0
