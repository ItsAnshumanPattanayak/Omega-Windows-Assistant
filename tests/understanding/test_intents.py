import pytest

from omega.models import IntentType
from omega.understanding import CommandParser


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Open Chrome", IntentType.OPEN_APPLICATION),
        ("Launch Google Chrome", IntentType.OPEN_APPLICATION),
        ("Close Notepad", IntentType.CLOSE_APPLICATION),
        ("Is Edge running?", IntentType.CHECK_APPLICATION_STATUS),
        ("Create a folder named Projects", IntentType.CREATE_FOLDER),
        ("Make a directory called College Work", IntentType.CREATE_FOLDER),
        ("Create a text file named author", IntentType.CREATE_FILE),
        ("Open notes.txt", IntentType.OPEN_FILE),
        ("Read notes.txt", IntentType.READ_FILE),
        ('Write "Hello World" into notes.txt', IntentType.WRITE_FILE),
        ("Rename author.txt to writer.txt", IntentType.RENAME_FILE),
        ("Copy notes.txt to Documents", IntentType.COPY_FILE),
        ("Move notes.txt to Downloads", IntentType.MOVE_FILE),
        ("Delete author.txt", IntentType.DELETE_FILE),
        ("Find resume.pdf", IntentType.SEARCH_FILE),
        ("Open the Projects folder", IntentType.OPEN_FOLDER),
        ("Show files inside Downloads", IntentType.LIST_FOLDER),
        ("Rename Projects to College Projects", IntentType.RENAME_FOLDER),
        ("Delete the Test folder", IntentType.DELETE_FOLDER),
    ],
)
def test_supported_intents(text: str, intent: IntentType) -> None:
    assert CommandParser().parse(text).command.intent is intent
