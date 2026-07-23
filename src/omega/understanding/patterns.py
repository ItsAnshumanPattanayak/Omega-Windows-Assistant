"""Explicitly ordered intent patterns for Phase 3."""

from __future__ import annotations

import re
from dataclasses import dataclass

from omega.models import IntentType


@dataclass(frozen=True)
class IntentPattern:
    name: str
    intent: IntentType
    expression: re.Pattern[str]


def _rule(name: str, intent: IntentType, expression: str) -> IntentPattern:
    return IntentPattern(name, intent, re.compile(expression, re.IGNORECASE))


INTENT_PATTERNS = (
    _rule("open_browser", IntentType.OPEN_BROWSER, r"^open (?:the )?browser$"),
    _rule("close_browser", IntentType.CLOSE_BROWSER, r"^close (?:the )?browser$"),
    _rule(
        "open_website",
        IntentType.OPEN_WEBSITE,
        r"^(?:open|visit|go to) (?:the )?(?:website )?"
        r"(?:https?://\S+|(?:[a-z0-9-]+\s+dot\s+)+"
        r"(?:com|org|net|io|dev|edu|gov|co|ai|app|info|me|in|uk|us)|"
        r"(?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|edu|gov|co|ai|app|info|"
        r"me|in|uk|us)(?:/\S*)?)$",
    ),
    _rule(
        "search_web",
        IntentType.SEARCH_WEB,
        r"^(?:search (?:the )?web for|web search for) .+$",
    ),
    _rule("open_new_tab", IntentType.OPEN_NEW_TAB, r"^open (?:a )?new tab$"),
    _rule("close_tab", IntentType.CLOSE_TAB, r"^close tab(?: .+)?$"),
    _rule(
        "switch_tab",
        IntentType.SWITCH_TAB,
        r"^switch (?:to )?tab(?: .+)?$",
    ),
    _rule("list_tabs", IntentType.LIST_TABS, r"^(?:list|show) (?:open )?tabs$"),
    _rule("refresh_page", IntentType.REFRESH_PAGE, r"^refresh(?: the)? page$"),
    _rule("go_back", IntentType.GO_BACK, r"^go back$"),
    _rule("go_forward", IntentType.GO_FORWARD, r"^go forward$"),
    _rule(
        "page_information",
        IntentType.GET_PAGE_INFORMATION,
        r"^(?:get|show) (?:page information|page info|current url|page title)$",
    ),
    _rule(
        "find_text_on_page",
        IntentType.FIND_TEXT_ON_PAGE,
        r"^find (?:the )?(?:word|text) .+ on (?:this|the) page$",
    ),
    _rule("open_bookmark", IntentType.OPEN_BOOKMARK, r"^open bookmark .+$"),
    _rule(
        "save_bookmark",
        IntentType.SAVE_BOOKMARK,
        r"^save (?:this page as |bookmark )(?:bookmark )?.+$",
    ),
    _rule(
        "show_history",
        IntentType.SHOW_HISTORY,
        r"^show (?:history|recent commands|recent actions|failed actions|"
        r"actions for the last command)$",
    ),
    _rule("clear_history", IntentType.CLEAR_HISTORY, r"^clear history$"),
    _rule("export_history", IntentType.EXPORT_HISTORY, r"^export history$"),
    _rule("undo", IntentType.UNDO_LAST_ACTION, r"^undo(?: last action)?$"),
    _rule("help", IntentType.HELP, r"^(?:show )?help$"),
    _rule("shutdown", IntentType.SHUTDOWN_ASSISTANT, r"^shut down omega$"),
    _rule(
        "app_status",
        IntentType.CHECK_APPLICATION_STATUS,
        r"^(?:is .+ running|check (?:whether )?.+(?: is running| status))$",
    ),
    _rule(
        "file_exists",
        IntentType.CHECK_FILE_EXISTENCE,
        r"^(?:does .+ exist(?: (?:on|in) .+)?|"
        r"check whether .+ exists?(?: (?:on|in) .+)?|"
        r"is there (?:a )?(?:folder|directory) named .+)$",
    ),
    _rule(
        "file_information",
        IntentType.GET_FILE_INFORMATION,
        r"^(?:show (?:information|info) about|"
        r"get (?:information|info) (?:about|for)|how large is|"
        r"count (?:the )?items inside) .+$",
    ),
    _rule(
        "create_folder",
        IntentType.CREATE_FOLDER,
        r"^(?:create|make) (?:a )?(?:folder|directory)(?: named| called)?(?: .+)?$",
    ),
    _rule(
        "list_folder",
        IntentType.LIST_FOLDER,
        r"^(?:show (?:files|the contents) inside|show (?:the )?contents of|"
        r"list (?:files inside|(?:the )?contents of)|what is inside) .+$",
    ),
    _rule("rename", IntentType.RENAME_FILE, r"^rename .+ to .+$"),
    _rule("rename_incomplete", IntentType.RENAME_FILE, r"^rename .+$"),
    _rule("copy", IntentType.COPY_FILE, r"^copy .+ to .+$"),
    _rule("move", IntentType.MOVE_FILE, r"^move .+(?: to .+)?$"),
    _rule("append", IntentType.APPEND_FILE, r"^append(?: .+)? (?:to|into)(?: .+)?$"),
    _rule("write", IntentType.WRITE_FILE, r"^write(?: .+)? into(?: .+)?$"),
    _rule(
        "folder_search",
        IntentType.SEARCH_FOLDER,
        r"^(?:find|search for) (?:(?:a )?folders?(?: named)? .+|"
        r"(?:the )?.+ folder(?: (?:on|in) .+)?)$",
    ),
    _rule("search", IntentType.SEARCH_FILE, r"^(?:find|search for) .+$"),
    _rule(
        "read",
        IntentType.READ_FILE,
        r"^(?:read(?: the file)?(?: .+)?|show (?:the )?contents of .+)$",
    ),
    _rule("delete", IntentType.DELETE_FILE, r"^delete(?: the)?(?: .+)?$"),
    _rule(
        "create_file",
        IntentType.CREATE_FILE,
        r"^create (?!.*\bfolder\b|.*\bdirectory\b)"
        r"(?:(?:a )?(?:(?:text|markdown|json|csv|python|html|"
        r"css|javascript|yaml) )?file"
        r"(?: named| called)?(?: .+)?|"
        r".+\.[a-z0-9]+(?:\s+(?:in|on)\s+.+)?)$",
    ),
    _rule("open", IntentType.OPEN_APPLICATION, r"^(?:open|launch|start|run)(?: .+)?$"),
    _rule("close", IntentType.CLOSE_APPLICATION, r"^(?:close|exit|quit)(?: .+)?$"),
)
