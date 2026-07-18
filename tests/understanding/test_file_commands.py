import pytest

from omega.models import IntentType
from omega.understanding import CommandParser


@pytest.mark.parametrize(
    ("text", "intent", "expected"),
    [
        (
            "Create a text file named author on Desktop",
            IntentType.CREATE_FILE,
            {"file_name": "author", "file_extension": ".txt", "location": "desktop"},
        ),
        (
            "Create notes.md in Documents",
            IntentType.CREATE_FILE,
            {"file_name": "notes.md", "location": "documents"},
        ),
        (
            'Write "Hello World" into notes.txt',
            IntentType.WRITE_FILE,
            {"file_name": "notes.txt", "text_content": "Hello World"},
        ),
        (
            'Append "Second line" to notes.txt',
            IntentType.APPEND_FILE,
            {"file_name": "notes.txt", "text_content": "Second line"},
        ),
        (
            "Read notes.txt from Documents",
            IntentType.READ_FILE,
            {"file_name": "notes.txt", "location": "documents"},
        ),
        (
            "Rename notes.md in Documents to study-notes.md",
            IntentType.RENAME_FILE,
            {
                "source_file": "notes.md",
                "new_name": "study-notes.md",
                "location": "documents",
            },
        ),
        (
            "Copy writer.txt from Desktop to Documents",
            IntentType.COPY_FILE,
            {
                "source_file": "writer.txt",
                "source_location": "desktop",
                "destination": "documents",
            },
        ),
        (
            "Move writer.txt from Documents to Downloads",
            IntentType.MOVE_FILE,
            {
                "source_file": "writer.txt",
                "source_location": "documents",
                "destination": "downloads",
            },
        ),
        (
            "Open resume.pdf from Documents",
            IntentType.OPEN_FILE,
            {"file_name": "resume.pdf", "location": "documents"},
        ),
        (
            "Find Python files in Downloads",
            IntentType.SEARCH_FILE,
            {"search_extension": ".py", "location": "downloads"},
        ),
        (
            "Does author.txt exist on Desktop?",
            IntentType.CHECK_FILE_EXISTENCE,
            {"file_name": "author.txt", "location": "desktop"},
        ),
        (
            "Show information about notes.txt",
            IntentType.GET_FILE_INFORMATION,
            {"file_name": "notes.txt"},
        ),
    ],
)
def test_phase5_commands_extract_canonical_entities(
    text: str, intent: IntentType, expected: dict[str, str]
) -> None:
    result = CommandParser().parse(text)
    values = {entity.name: entity.value for entity in result.command.entities}
    assert result.command.intent is intent
    assert not result.requires_clarification
    assert expected.items() <= values.items()


def test_quoted_content_is_preserved_exactly_and_missing_values_clarify() -> None:
    result = CommandParser().parse('Write "  Keep THIS  " into Notes.txt')
    values = {entity.name: entity.value for entity in result.command.entities}
    assert values["text_content"] == "  Keep THIS  "
    assert CommandParser().parse("Append to notes.txt").requires_clarification
    assert CommandParser().parse("Search for").command.intent is IntentType.UNKNOWN
