from omega.database.schema import LATEST_SCHEMA_VERSION, PRODUCTIVITY_SCHEMA_VERSION
from omega.models import IntentType
from omega.understanding import CommandParser


def test_phase16_is_contiguous_schema_version() -> None:
    assert PRODUCTIVITY_SCHEMA_VERSION == 7
    assert LATEST_SCHEMA_VERSION == 7


def test_productivity_commands_use_the_existing_parser() -> None:
    parser = CommandParser()
    cases = {
        "Create a note called Project Ideas": IntentType.CREATE_NOTE,
        "Show my notes": IntentType.LIST_NOTES,
        "Search my notes for SQLite": IntentType.SEARCH_NOTES,
        "Create a task list called Work": IntentType.CREATE_TASK_LIST,
        "Create a task to finish documentation": IntentType.CREATE_TASK,
        "Show my tasks": IntentType.LIST_TASKS,
        "Show overdue tasks": IntentType.SHOW_OVERDUE_TASKS,
        "Mark the documentation task complete": IntentType.COMPLETE_TASK,
        "Set the documentation task priority to high": IntentType.SET_TASK_PRIORITY,
    }
    for text, intent in cases.items():
        result = parser.parse(text)
        assert result.command.intent is intent
        assert not result.requires_clarification


def test_note_code_and_task_shell_text_remain_entities() -> None:
    note = CommandParser().parse(
        'Create a note called Example with ```python\nprint("never")\n```'
    )
    task = CommandParser().parse("Create a task to run powershell later")
    assert note.command.intent is IntentType.CREATE_NOTE
    assert task.command.intent is IntentType.CREATE_TASK
    assert all(not callable(item.value) for item in note.command.entities)
