import pytest

from omega.models import IntentType
from omega.understanding import CommandParser


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("copy hello to clipboard", IntentType.COPY_TEXT_TO_CLIPBOARD),
        ("read the clipboard", IntentType.READ_CLIPBOARD),
        ("clear my clipboard", IntentType.CLEAR_CLIPBOARD),
        ("search clipboard for hello", IntentType.SEARCH_CLIPBOARD),
        ("save clipboard to clip.txt", IntentType.SAVE_CLIPBOARD_TO_FILE),
        ("take a screenshot", IntentType.CAPTURE_SCREENSHOT),
        ("capture virtual desktop", IntentType.CAPTURE_SCREENSHOT),
        ("list recent screenshots", IntentType.LIST_SCREENSHOTS),
        ("show screen information", IntentType.SHOW_DISPLAY_INFORMATION),
        ("show active window", IntentType.SHOW_ACTIVE_WINDOW),
        ("list visible windows", IntentType.LIST_VISIBLE_WINDOWS),
        ("find window named Editor", IntentType.FIND_WINDOW),
    ],
)
def test_desktop_intents(text: str, intent: IntentType) -> None:
    result = CommandParser().parse(text)
    assert result.matched and result.command.intent is intent


def test_clipboard_text_is_preserved_as_entity() -> None:
    result = CommandParser().parse("copy My Exact Text to clipboard")
    assert result.command.entities[0].value == "My Exact Text"


def test_region_is_structured_without_capture() -> None:
    result = CommandParser().parse("capture region 1 2 30 40")
    assert [entity.value for entity in result.command.entities] == [1, 2, 30, 40]
