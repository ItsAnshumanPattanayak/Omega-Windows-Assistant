"""Shared parser coverage for browser commands and dangerous exclusions."""

import pytest

from omega.models import CommandSource, EntityType, IntentType
from omega.understanding import CommandParser


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Open the browser", IntentType.OPEN_BROWSER),
        ("Close browser", IntentType.CLOSE_BROWSER),
        ("Open https://example.com/docs", IntentType.OPEN_WEBSITE),
        ("Open example dot com", IntentType.OPEN_WEBSITE),
        ("Search the web for Python decorators", IntentType.SEARCH_WEB),
        ("Open a new tab", IntentType.OPEN_NEW_TAB),
        ("Close tab two", IntentType.CLOSE_TAB),
        ("Switch to tab 1", IntentType.SWITCH_TAB),
        ("List tabs", IntentType.LIST_TABS),
        ("Refresh the page", IntentType.REFRESH_PAGE),
        ("Go back", IntentType.GO_BACK),
        ("Go forward", IntentType.GO_FORWARD),
        ("Get page information", IntentType.GET_PAGE_INFORMATION),
        ("Find the word installation on this page", IntentType.FIND_TEXT_ON_PAGE),
        ("Open bookmark Documentation", IntentType.OPEN_BOOKMARK),
        ("Save this page as Documentation", IntentType.SAVE_BOOKMARK),
    ],
)
def test_browser_commands_use_existing_parser(text: str, intent: IntentType) -> None:
    result = CommandParser().parse(text, source=CommandSource.VOICE)
    assert result.command.intent is intent
    assert result.command.source is CommandSource.VOICE
    assert result.matched
    assert not result.requires_clarification


def test_spoken_domain_is_conservatively_normalized() -> None:
    result = CommandParser().parse("Open example dot com")
    entity = result.command.entities[0]
    assert entity.entity_type is EntityType.URL
    assert entity.value == "https://example.com"


def test_search_query_and_tab_reference_are_extracted() -> None:
    search = CommandParser().parse("Search the web for Python typing")
    assert search.command.entities[0].value == "Python typing"
    tab = CommandParser().parse("Switch to tab two")
    assert tab.command.entities[0].value == "2"


@pytest.mark.parametrize(
    "text",
    [
        "Enter my password",
        "Submit payment",
        "Bypass captcha",
        "Install extension",
        "javascript:alert(1)",
    ],
)
def test_dangerous_browser_requests_remain_unknown(text: str) -> None:
    result = CommandParser().parse(text)
    assert result.command.intent is IntentType.UNKNOWN
    assert "unsupported_or_dangerous" in result.warnings


def test_existing_file_open_is_not_misclassified_as_website() -> None:
    assert (
        CommandParser().parse("Open notes.txt").command.intent is IntentType.OPEN_FILE
    )
