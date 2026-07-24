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
    _rule(
        "create_knowledge_collection",
        IntentType.CREATE_KNOWLEDGE_COLLECTION,
        r"^create (?:a )?knowledge collection(?: called| named)? .+$",
    ),
    _rule(
        "list_knowledge_collections",
        IntentType.LIST_KNOWLEDGE_COLLECTIONS,
        r"^(?:show|list) (?:my )?knowledge collections$",
    ),
    _rule(
        "show_knowledge_collection",
        IntentType.SHOW_KNOWLEDGE_COLLECTION,
        r"^show (?:the )?.+ knowledge collection$",
    ),
    _rule(
        "update_knowledge_collection",
        IntentType.UPDATE_KNOWLEDGE_COLLECTION,
        r"^(?:rename|update) (?:the )?.+ knowledge collection (?:to|with) .+$",
    ),
    _rule(
        "archive_knowledge_collection",
        IntentType.ARCHIVE_KNOWLEDGE_COLLECTION,
        r"^archive (?:the )?.+ knowledge collection$",
    ),
    _rule(
        "restore_knowledge_collection",
        IntentType.RESTORE_KNOWLEDGE_COLLECTION,
        r"^restore (?:the )?.+ knowledge collection$",
    ),
    _rule(
        "delete_knowledge_collection",
        IntentType.DELETE_KNOWLEDGE_COLLECTION,
        r"^delete (?:the )?.+ knowledge collection$",
    ),
    _rule(
        "import_knowledge_document",
        IntentType.IMPORT_KNOWLEDGE_DOCUMENT,
        r"^(?:import|add) .+\.(?:pdf|docx|txt|md|markdown)(?: .*)?$",
    ),
    _rule(
        "list_knowledge_documents",
        IntentType.LIST_KNOWLEDGE_DOCUMENTS,
        r"^(?:show|list) (?:my )?(?:knowledge )?documents(?: in .+)?$",
    ),
    _rule(
        "show_knowledge_document",
        IntentType.SHOW_KNOWLEDGE_DOCUMENT,
        r"^show (?:the )?.+ (?:knowledge )?document$",
    ),
    _rule(
        "move_knowledge_document",
        IntentType.MOVE_KNOWLEDGE_DOCUMENT,
        r"^move (?:the )?.+ document to .+(?: collection)?$",
    ),
    _rule(
        "reindex_knowledge_document",
        IntentType.REINDEX_KNOWLEDGE_DOCUMENT,
        r"^re-?index (?:the )?.+ document$",
    ),
    _rule(
        "remove_knowledge_document",
        IntentType.REMOVE_KNOWLEDGE_DOCUMENT,
        r"^(?:remove|delete) (?:the )?.+ document from (?:my )?knowledge base$",
    ),
    _rule(
        "search_knowledge",
        IntentType.SEARCH_KNOWLEDGE,
        r"^search (?:(?:my documents|my knowledge base)|"
        r"(?!(?:the web|web|my notes|notes|my tasks|tasks)\b).+) for .+$",
    ),
    _rule(
        "ask_knowledge",
        IntentType.ASK_KNOWLEDGE,
        r"^(?:ask (?:my documents|my knowledge base)|what does .+ "
        r"(?:document|pdf|docx) say about) .+$",
    ),
    _rule(
        "show_knowledge_sources",
        IntentType.SHOW_KNOWLEDGE_SOURCES,
        r"^show (?:the )?sources for (?:that|the last) answer$",
    ),
    _rule(
        "export_knowledge_results",
        IntentType.EXPORT_KNOWLEDGE_RESULTS,
        r"^export (?:these|the last|my knowledge) (?:search )?results$",
    ),
    _rule("list_notes", IntentType.LIST_NOTES, r"^(?:show|list) (?:my )?notes$"),
    _rule("search_notes", IntentType.SEARCH_NOTES, r"^search (?:my )?notes for .+$"),
    _rule("show_note", IntentType.SHOW_NOTE, r"^(?:show|open|view) (?:the )?.+ note$"),
    _rule(
        "append_note",
        IntentType.APPEND_NOTE,
        r"^(?:add|append) .+ to (?:the )?.+ note$",
    ),
    _rule(
        "update_note",
        IntentType.UPDATE_NOTE,
        r"^update (?:the )?.+ note(?: to| with) .+$",
    ),
    _rule("pin_note", IntentType.PIN_NOTE, r"^pin (?:the )?.+ note$"),
    _rule("unpin_note", IntentType.UNPIN_NOTE, r"^unpin (?:the )?.+ note$"),
    _rule("archive_note", IntentType.ARCHIVE_NOTE, r"^archive (?:the )?.+ note$"),
    _rule("restore_note", IntentType.RESTORE_NOTE, r"^restore (?:the )?.+ note$"),
    _rule("delete_note", IntentType.DELETE_NOTE, r"^delete (?:the )?.+ note$"),
    _rule("tag_note", IntentType.TAG_NOTE, r"^tag (?:the )?.+ note with .+$"),
    _rule(
        "untag_note", IntentType.UNTAG_NOTE, r"^remove tag .+ from (?:the )?.+ note$"
    ),
    _rule(
        "create_note",
        IntentType.CREATE_NOTE,
        r"^create (?:a )?note(?: called| titled| named)? .+$",
    ),
    _rule("export_notes", IntentType.EXPORT_NOTES, r"^export notes(?: to .+)?$"),
    _rule("import_notes", IntentType.IMPORT_NOTES, r"^import notes from .+$"),
    _rule("list_task_lists", IntentType.LIST_TASK_LISTS, r"^(?:show|list) task lists$"),
    _rule(
        "create_task_list",
        IntentType.CREATE_TASK_LIST,
        r"^create (?:a )?task list(?: called| named)? .+$",
    ),
    _rule("show_task_list", IntentType.SHOW_TASK_LIST, r"^show (?:the )?.+ task list$"),
    _rule(
        "update_task_list",
        IntentType.UPDATE_TASK_LIST,
        r"^(?:rename|update) (?:the )?.+ task list (?:to|with) .+$",
    ),
    _rule(
        "archive_task_list",
        IntentType.ARCHIVE_TASK_LIST,
        r"^archive (?:the )?.+ task list$",
    ),
    _rule(
        "restore_task_list",
        IntentType.RESTORE_TASK_LIST,
        r"^restore (?:the )?.+ task list$",
    ),
    _rule(
        "delete_task_list",
        IntentType.DELETE_TASK_LIST,
        r"^delete (?:the )?.+ task list$",
    ),
    _rule("show_overdue_tasks", IntentType.SHOW_OVERDUE_TASKS, r"^show overdue tasks$"),
    _rule("show_due_tasks", IntentType.SHOW_DUE_TASKS, r"^show tasks due today$"),
    _rule("list_tasks", IntentType.LIST_TASKS, r"^(?:show|list) (?:my )?tasks$"),
    _rule("search_tasks", IntentType.SEARCH_TASKS, r"^search (?:my )?tasks for .+$"),
    _rule(
        "complete_task",
        IntentType.COMPLETE_TASK,
        r"^(?:mark|complete) (?:the )?.+ task(?: complete)?$",
    ),
    _rule("reopen_task", IntentType.REOPEN_TASK, r"^reopen (?:the )?.+ task$"),
    _rule("cancel_task", IntentType.CANCEL_TASK, r"^cancel (?:the )?.+ task$"),
    _rule("archive_task", IntentType.ARCHIVE_TASK, r"^archive (?:the )?.+ task$"),
    _rule("restore_task", IntentType.RESTORE_TASK, r"^restore (?:the )?.+ task$"),
    _rule("delete_task", IntentType.DELETE_TASK, r"^delete (?:the )?.+ task$"),
    _rule(
        "set_task_priority",
        IntentType.SET_TASK_PRIORITY,
        r"^set (?:the )?.+ task priority to (?:none|low|medium|high|urgent)$",
    ),
    _rule(
        "set_task_deadline",
        IntentType.SET_TASK_DEADLINE,
        r"^set (?:the )?.+ task deadline to .+$",
    ),
    _rule(
        "remove_task_deadline",
        IntentType.REMOVE_TASK_DEADLINE,
        r"^remove (?:the )?.+ task deadline$",
    ),
    _rule("move_task", IntentType.MOVE_TASK, r"^move (?:the )?.+ task to .+$"),
    _rule("tag_task", IntentType.TAG_TASK, r"^tag (?:the )?.+ task with .+$"),
    _rule(
        "untag_task", IntentType.UNTAG_TASK, r"^remove tag .+ from (?:the )?.+ task$"
    ),
    _rule(
        "link_task_reminder",
        IntentType.LINK_TASK_REMINDER,
        r"^(?:link reminder .+ to|remind me about) (?:the )?.+ task(?: at .+)?$",
    ),
    _rule(
        "unlink_task_reminder",
        IntentType.UNLINK_TASK_REMINDER,
        r"^unlink reminder .+ from (?:the )?.+ task$",
    ),
    _rule("show_task", IntentType.SHOW_TASK, r"^(?:show|view) (?:the )?.+ task$"),
    _rule(
        "update_task",
        IntentType.UPDATE_TASK,
        r"^update (?:the )?.+ task(?: to| with) .+$",
    ),
    _rule(
        "create_task",
        IntentType.CREATE_TASK,
        r"^(?:create|add) (?:a )?task(?: to .+ list)?(?: to)? .+$",
    ),
    _rule(
        "create_task_incomplete",
        IntentType.CREATE_TASK,
        r"^(?:create|add) (?:a )?task(?: to .+ list)?$",
    ),
    _rule(
        "update_reminder",
        IntentType.UPDATE_REMINDER,
        r"^(?:update|reschedule) (?:the )?(?:.+ )?reminder(?: .+)?$",
    ),
    _rule(
        "show_reminder",
        IntentType.SHOW_REMINDER,
        r"^(?:show|view) (?:the )?(?:.+ )?reminder(?: .+)?$",
    ),
    _rule(
        "cancel_reminder",
        IntentType.CANCEL_REMINDER,
        r"^cancel (?:the )?(?:.+ )?reminder(?: .+)?$",
    ),
    _rule(
        "complete_reminder",
        IntentType.COMPLETE_REMINDER,
        r"^(?:complete|mark) (?:the )?(?:.+ )?reminder(?: complete)?$",
    ),
    _rule(
        "update_alarm",
        IntentType.UPDATE_ALARM,
        r"^(?:update|reschedule) (?:the )?(?:.+ )?alarm(?: .+)?$",
    ),
    _rule(
        "show_alarm",
        IntentType.SHOW_ALARM,
        r"^(?:show|view) (?:the )?(?:.+ )?alarm(?: .+)?$",
    ),
    _rule(
        "cancel_alarm",
        IntentType.CANCEL_ALARM,
        r"^cancel (?:the )?(?:.+ )?alarm(?: .+)?$",
    ),
    _rule(
        "dismiss_alarm",
        IntentType.DISMISS_ALARM,
        r"^dismiss (?:the )?(?:.+ )?alarm$",
    ),
    _rule(
        "create_recurring_reminder",
        IntentType.CREATE_RECURRING_REMINDER,
        r"^remind me every .+$",
    ),
    _rule(
        "create_reminder",
        IntentType.CREATE_REMINDER,
        r"^remind me (?:at|in|tomorrow|on) .+$",
    ),
    _rule(
        "create_recurring_alarm",
        IntentType.CREATE_RECURRING_ALARM,
        r"^set (?:an )?alarm every .+$",
    ),
    _rule(
        "create_alarm", IntentType.CREATE_ALARM, r"^set (?:an )?alarm (?:for|at) .+$"
    ),
    _rule(
        "start_timer",
        IntentType.START_TIMER,
        r"^start (?:a |the )?(?:.+ )?timer for .+$",
    ),
    _rule("pause_timer", IntentType.PAUSE_TIMER, r"^pause (?:the )?.+ timer$"),
    _rule("resume_timer", IntentType.RESUME_TIMER, r"^resume (?:the )?.+ timer$"),
    _rule("cancel_timer", IntentType.CANCEL_TIMER, r"^cancel (?:the )?.+ timer$"),
    _rule("show_timer", IntentType.SHOW_TIMER, r"^show (?:the )?.+ timer$"),
    _rule("list_timers", IntentType.LIST_TIMERS, r"^list (?:active )?timers$"),
    _rule("list_reminders", IntentType.LIST_REMINDERS, r"^list reminders$"),
    _rule("list_alarms", IntentType.LIST_ALARMS, r"^list alarms$"),
    _rule(
        "list_schedules",
        IntentType.LIST_SCHEDULED_ITEMS,
        r"^list (?:scheduled items|schedules)$",
    ),
    _rule(
        "snooze_reminder",
        IntentType.SNOOZE_REMINDER,
        r"^snooze (?:this |the )?(?:.+ )?reminder(?: for .+)?$",
    ),
    _rule(
        "snooze_alarm",
        IntentType.SNOOZE_ALARM,
        r"^snooze (?:this |the )?(?:.+ )?alarm(?: for .+)?$",
    ),
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
        "system_information",
        IntentType.GET_SYSTEM_INFORMATION,
        r"^(?:show|get) system information$",
    ),
    _rule(
        "cpu_usage",
        IntentType.GET_CPU_USAGE,
        r"^(?:(?:show|what is) (?:my )?cpu usage|how busy is (?:my )?cpu)$",
    ),
    _rule(
        "memory_usage",
        IntentType.GET_MEMORY_USAGE,
        r"^(?:show memory usage|how much memory is available)$",
    ),
    _rule("disk_usage", IntentType.GET_DISK_USAGE, r"^(?:show|get) disk space$"),
    _rule(
        "battery_status",
        IntentType.GET_BATTERY_STATUS,
        r"^(?:show battery status|what is the battery percentage)$",
    ),
    _rule(
        "network_status",
        IntentType.GET_NETWORK_STATUS,
        r"^(?:show|get) network status$",
    ),
    _rule(
        "list_processes",
        IntentType.LIST_PROCESSES,
        r"^(?:list|show) running processes$",
    ),
    _rule(
        "search_process",
        IntentType.SEARCH_PROCESS,
        r"^(?:find|search for) (?:a )?process(?: named)? .+$",
    ),
    _rule(
        "process_information",
        IntentType.GET_PROCESS_INFORMATION,
        r"^show process information for .+$",
    ),
    _rule("get_volume", IntentType.GET_VOLUME, r"^(?:show|get) volume$"),
    _rule(
        "set_volume",
        IntentType.SET_VOLUME,
        r"^set (?:the )?volume to .+$",
    ),
    _rule(
        "increase_volume",
        IntentType.INCREASE_VOLUME,
        r"^(?:increase|raise|turn up) (?:the )?volume(?: by .+)?$",
    ),
    _rule(
        "decrease_volume",
        IntentType.DECREASE_VOLUME,
        r"^(?:decrease|lower|turn down) (?:the )?volume(?: by .+)?$",
    ),
    _rule("mute_volume", IntentType.MUTE_VOLUME, r"^mute (?:the )?(?:sound|volume)$"),
    _rule(
        "unmute_volume",
        IntentType.UNMUTE_VOLUME,
        r"^unmute (?:the )?(?:sound|volume)$",
    ),
    _rule(
        "get_brightness",
        IntentType.GET_BRIGHTNESS,
        r"^(?:show|get) brightness$",
    ),
    _rule(
        "set_brightness",
        IntentType.SET_BRIGHTNESS,
        r"^set (?:the )?brightness to .+$",
    ),
    _rule(
        "increase_brightness",
        IntentType.INCREASE_BRIGHTNESS,
        r"^(?:increase|raise) (?:the )?brightness(?: by .+)?$",
    ),
    _rule(
        "decrease_brightness",
        IntentType.DECREASE_BRIGHTNESS,
        r"^(?:decrease|lower) (?:the )?brightness(?: by .+)?$",
    ),
    _rule(
        "open_windows_settings",
        IntentType.OPEN_WINDOWS_SETTINGS,
        r"^open (?:system|display|sound|notifications|power(?: and battery)?|"
        r"storage|bluetooth(?: and devices)?|network(?: and internet)?|"
        r"windows update|apps|privacy) settings$",
    ),
    _rule("lock_computer", IntentType.LOCK_COMPUTER, r"^lock (?:the )?computer$"),
    _rule(
        "sleep_computer",
        IntentType.SLEEP_COMPUTER,
        r"^(?:put (?:the )?computer to sleep|sleep (?:the )?computer)$",
    ),
    _rule(
        "hibernate_computer",
        IntentType.HIBERNATE_COMPUTER,
        r"^hibernate (?:the )?computer$",
    ),
    _rule("sign_out_user", IntentType.SIGN_OUT_USER, r"^sign out$"),
    _rule(
        "restart_computer",
        IntentType.RESTART_COMPUTER,
        r"^restart (?:the )?computer$",
    ),
    _rule(
        "shutdown_computer",
        IntentType.SHUT_DOWN_COMPUTER,
        r"^shut down (?:the )?computer$",
    ),
    _rule(
        "cancel_power_action",
        IntentType.CANCEL_POWER_ACTION,
        r"^cancel (?:the )?(?:shutdown|restart|power action)$",
    ),
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
