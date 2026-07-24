"""Deterministic and conservative risk classification."""

from __future__ import annotations

from omega.models import IntentType, RiskLevel
from omega.safety.models import SafetyContext

_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}

_LOW = frozenset(
    {
        IntentType.CHECK_APPLICATION_STATUS,
        IntentType.READ_FILE,
        IntentType.OPEN_FILE,
        IntentType.SEARCH_FILE,
        IntentType.CHECK_FILE_EXISTENCE,
        IntentType.GET_FILE_INFORMATION,
        IntentType.OPEN_FOLDER,
        IntentType.LIST_FOLDER,
        IntentType.SEARCH_FOLDER,
        IntentType.CHECK_FOLDER_EXISTENCE,
        IntentType.GET_FOLDER_INFORMATION,
        IntentType.SHOW_HISTORY,
        IntentType.CLOSE_TAB,
        IntentType.LIST_TABS,
        IntentType.REFRESH_PAGE,
        IntentType.GO_BACK,
        IntentType.GO_FORWARD,
        IntentType.GET_PAGE_INFORMATION,
        IntentType.FIND_TEXT_ON_PAGE,
        IntentType.GET_SYSTEM_INFORMATION,
        IntentType.GET_CPU_USAGE,
        IntentType.GET_MEMORY_USAGE,
        IntentType.GET_DISK_USAGE,
        IntentType.GET_BATTERY_STATUS,
        IntentType.GET_NETWORK_STATUS,
        IntentType.LIST_PROCESSES,
        IntentType.SEARCH_PROCESS,
        IntentType.GET_PROCESS_INFORMATION,
        IntentType.GET_VOLUME,
        IntentType.GET_BRIGHTNESS,
        IntentType.OPEN_WINDOWS_SETTINGS,
        IntentType.CANCEL_POWER_ACTION,
        IntentType.CREATE_REMINDER,
        IntentType.CREATE_ALARM,
        IntentType.START_TIMER,
        IntentType.LIST_REMINDERS,
        IntentType.LIST_ALARMS,
        IntentType.LIST_TIMERS,
        IntentType.LIST_SCHEDULED_ITEMS,
        IntentType.SHOW_REMINDER,
        IntentType.SHOW_ALARM,
        IntentType.SHOW_TIMER,
        IntentType.CREATE_NOTE,
        IntentType.LIST_NOTES,
        IntentType.SHOW_NOTE,
        IntentType.SEARCH_NOTES,
        IntentType.PIN_NOTE,
        IntentType.UNPIN_NOTE,
        IntentType.CREATE_TASK_LIST,
        IntentType.LIST_TASK_LISTS,
        IntentType.SHOW_TASK_LIST,
        IntentType.CREATE_TASK,
        IntentType.LIST_TASKS,
        IntentType.SHOW_TASK,
        IntentType.COMPLETE_TASK,
        IntentType.REOPEN_TASK,
        IntentType.SET_TASK_PRIORITY,
        IntentType.SET_TASK_DEADLINE,
        IntentType.REMOVE_TASK_DEADLINE,
        IntentType.SEARCH_TASKS,
        IntentType.SHOW_DUE_TASKS,
        IntentType.SHOW_OVERDUE_TASKS,
        IntentType.LIST_KNOWLEDGE_COLLECTIONS,
        IntentType.SHOW_KNOWLEDGE_COLLECTION,
        IntentType.LIST_KNOWLEDGE_DOCUMENTS,
        IntentType.SHOW_KNOWLEDGE_DOCUMENT,
        IntentType.SEARCH_KNOWLEDGE,
        IntentType.ASK_KNOWLEDGE,
        IntentType.SHOW_KNOWLEDGE_SOURCES,
    }
)
_MEDIUM = frozenset(
    {
        IntentType.OPEN_APPLICATION,
        IntentType.CREATE_FILE,
        IntentType.APPEND_FILE,
        IntentType.RENAME_FILE,
        IntentType.COPY_FILE,
        IntentType.CREATE_FOLDER,
        IntentType.RENAME_FOLDER,
        IntentType.COPY_FOLDER,
        IntentType.EXPORT_HISTORY,
        IntentType.OPEN_BROWSER,
        IntentType.OPEN_WEBSITE,
        IntentType.SEARCH_WEB,
        IntentType.OPEN_NEW_TAB,
        IntentType.SWITCH_TAB,
        IntentType.OPEN_BOOKMARK,
        IntentType.SET_VOLUME,
        IntentType.INCREASE_VOLUME,
        IntentType.DECREASE_VOLUME,
        IntentType.MUTE_VOLUME,
        IntentType.UNMUTE_VOLUME,
        IntentType.SET_BRIGHTNESS,
        IntentType.INCREASE_BRIGHTNESS,
        IntentType.DECREASE_BRIGHTNESS,
        IntentType.CREATE_RECURRING_REMINDER,
        IntentType.CREATE_RECURRING_ALARM,
        IntentType.PAUSE_TIMER,
        IntentType.RESUME_TIMER,
        IntentType.CANCEL_TIMER,
        IntentType.SNOOZE_REMINDER,
        IntentType.SNOOZE_ALARM,
        IntentType.UPDATE_REMINDER,
        IntentType.CANCEL_REMINDER,
        IntentType.COMPLETE_REMINDER,
        IntentType.UPDATE_ALARM,
        IntentType.CANCEL_ALARM,
        IntentType.DISMISS_ALARM,
        IntentType.UPDATE_NOTE,
        IntentType.APPEND_NOTE,
        IntentType.TAG_NOTE,
        IntentType.UNTAG_NOTE,
        IntentType.ARCHIVE_NOTE,
        IntentType.RESTORE_NOTE,
        IntentType.UPDATE_TASK_LIST,
        IntentType.ARCHIVE_TASK_LIST,
        IntentType.RESTORE_TASK_LIST,
        IntentType.UPDATE_TASK,
        IntentType.CANCEL_TASK,
        IntentType.ARCHIVE_TASK,
        IntentType.RESTORE_TASK,
        IntentType.MOVE_TASK,
        IntentType.TAG_TASK,
        IntentType.UNTAG_TASK,
        IntentType.LINK_TASK_REMINDER,
        IntentType.UNLINK_TASK_REMINDER,
        IntentType.EXPORT_NOTES,
        IntentType.IMPORT_NOTES,
        IntentType.CREATE_KNOWLEDGE_COLLECTION,
        IntentType.UPDATE_KNOWLEDGE_COLLECTION,
        IntentType.ARCHIVE_KNOWLEDGE_COLLECTION,
        IntentType.RESTORE_KNOWLEDGE_COLLECTION,
        IntentType.IMPORT_KNOWLEDGE_DOCUMENT,
        IntentType.MOVE_KNOWLEDGE_DOCUMENT,
        IntentType.REINDEX_KNOWLEDGE_DOCUMENT,
        IntentType.EXPORT_KNOWLEDGE_RESULTS,
    }
)
_HIGH = frozenset(
    {
        IntentType.CLOSE_APPLICATION,
        IntentType.WRITE_FILE,
        IntentType.MOVE_FILE,
        IntentType.MOVE_FOLDER,
        IntentType.UNDO_LAST_ACTION,
        IntentType.CLEAR_HISTORY,
        IntentType.CLOSE_BROWSER,
        IntentType.SAVE_BOOKMARK,
        IntentType.LOCK_COMPUTER,
        IntentType.SLEEP_COMPUTER,
        IntentType.HIBERNATE_COMPUTER,
        IntentType.DELETE_NOTE,
        IntentType.DELETE_TASK,
        IntentType.DELETE_TASK_LIST,
        IntentType.REMOVE_KNOWLEDGE_DOCUMENT,
        IntentType.DELETE_KNOWLEDGE_COLLECTION,
    }
)
_CRITICAL = frozenset(
    {
        IntentType.DELETE_FILE,
        IntentType.DELETE_FOLDER,
        IntentType.SIGN_OUT_USER,
        IntentType.RESTART_COMPUTER,
        IntentType.SHUT_DOWN_COMPUTER,
    }
)


class RiskClassifier:
    """Classify using only typed intent and validated target state."""

    def classify(self, context: SafetyContext) -> RiskLevel:
        intent = context.action.intent
        if context.additional_context.get("protected_resource") is True:
            computed = RiskLevel.CRITICAL
        elif context.additional_context.get("shell_like") is True:
            computed = RiskLevel.CRITICAL
        elif context.additional_context.get("destination_conflict") is True:
            computed = RiskLevel.HIGH
        elif intent in _LOW:
            computed = RiskLevel.LOW
        elif intent in _MEDIUM:
            computed = RiskLevel.MEDIUM
        elif intent is IntentType.WRITE_FILE and not context.additional_context.get(
            "target_has_content", context.target_exists
        ):
            computed = RiskLevel.MEDIUM
        elif intent in _HIGH:
            computed = RiskLevel.HIGH
        elif intent in _CRITICAL or intent is IntentType.UNKNOWN:
            computed = RiskLevel.CRITICAL
        else:
            computed = RiskLevel.CRITICAL
        provisional = context.action.risk_level
        return provisional if _ORDER[provisional] > _ORDER[computed] else computed
