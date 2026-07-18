import pytest

from omega.models import IntentType
from omega.understanding import CommandParser


@pytest.mark.parametrize(
    ("text", "intent", "expected"),
    [
        (
            "Create a folder named Projects on Desktop",
            IntentType.CREATE_FOLDER,
            {"folder_name": "Projects", "location": "desktop"},
        ),
        (
            "Create a folder named Notes inside Documents/College",
            IntentType.CREATE_FOLDER,
            {"folder_name": "Notes", "location": "documents", "parent_path": "College"},
        ),
        (
            "Open the Projects folder on Desktop",
            IntentType.OPEN_FOLDER,
            {"folder_name": "Projects", "location": "desktop"},
        ),
        ("Open Downloads", IntentType.OPEN_FOLDER, {"location": "downloads"}),
        (
            "List files inside Downloads",
            IntentType.LIST_FOLDER,
            {"location": "downloads"},
        ),
        (
            "Count items inside Downloads",
            IntentType.GET_FOLDER_INFORMATION,
            {"location": "downloads"},
        ),
        (
            "Does the Projects folder exist on Desktop?",
            IntentType.CHECK_FOLDER_EXISTENCE,
            {"folder_name": "Projects", "location": "desktop"},
        ),
        (
            "Is there a folder named Assignments in Documents/College?",
            IntentType.CHECK_FOLDER_EXISTENCE,
            {"folder_name": "College/Assignments", "location": "documents"},
        ),
        (
            "How large is the Projects folder?",
            IntentType.GET_FOLDER_INFORMATION,
            {"folder_name": "Projects", "recursive": True},
        ),
        (
            "Rename Projects to Omega Projects on Desktop",
            IntentType.RENAME_FOLDER,
            {
                "source_folder": "Projects",
                "new_name": "Omega Projects",
                "location": "desktop",
            },
        ),
        (
            "Copy Documents/College/Notes to Desktop",
            IntentType.COPY_FOLDER,
            {
                "source_folder": "College/Notes",
                "source_location": "documents",
                "destination": "desktop",
            },
        ),
        (
            "Move the Projects folder from Documents to Downloads",
            IntentType.MOVE_FOLDER,
            {
                "source_folder": "Projects",
                "source_location": "documents",
                "destination": "downloads",
            },
        ),
        (
            "Find a folder named College in Documents",
            IntentType.SEARCH_FOLDER,
            {"folder_name": "College", "location": "documents"},
        ),
        (
            "Search for the Projects folder on Desktop",
            IntentType.SEARCH_FOLDER,
            {"folder_name": "Projects", "location": "desktop"},
        ),
        (
            "Delete the Projects folder",
            IntentType.DELETE_FOLDER,
            {"folder_name": "Projects"},
        ),
    ],
)
def test_folder_commands_extract_canonical_entities(
    text: str, intent: IntentType, expected: dict[str, object]
) -> None:
    result = CommandParser().parse(text)
    values = {entity.name: entity.value for entity in result.command.entities}
    assert result.command.intent is intent
    assert not result.requires_clarification
    assert expected.items() <= values.items()
