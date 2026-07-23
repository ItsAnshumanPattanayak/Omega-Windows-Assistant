"""Stable serialized enumerations for Omega's future command lifecycle."""

from __future__ import annotations

from enum import StrEnum


class IntentType(StrEnum):
    """Future command intents; values are stable machine-readable identifiers."""

    UNKNOWN = "unknown"
    HELP = "help"
    ACTIVATE_ASSISTANT = "activate_assistant"
    SHUTDOWN_ASSISTANT = "shutdown_assistant"
    OPEN_APPLICATION = "open_application"
    CLOSE_APPLICATION = "close_application"
    CHECK_APPLICATION_STATUS = "check_application_status"
    CREATE_FILE = "create_file"
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    APPEND_FILE = "append_file"
    RENAME_FILE = "rename_file"
    COPY_FILE = "copy_file"
    MOVE_FILE = "move_file"
    DELETE_FILE = "delete_file"
    OPEN_FILE = "open_file"
    SEARCH_FILE = "search_file"
    CHECK_FILE_EXISTENCE = "check_file_existence"
    GET_FILE_INFORMATION = "get_file_information"
    CREATE_FOLDER = "create_folder"
    OPEN_FOLDER = "open_folder"
    LIST_FOLDER = "list_folder"
    RENAME_FOLDER = "rename_folder"
    COPY_FOLDER = "copy_folder"
    MOVE_FOLDER = "move_folder"
    DELETE_FOLDER = "delete_folder"
    CHECK_FOLDER_EXISTENCE = "check_folder_existence"
    GET_FOLDER_INFORMATION = "get_folder_information"
    SEARCH_FOLDER = "search_folder"
    UNDO_LAST_ACTION = "undo_last_action"
    SHOW_HISTORY = "show_history"
    CLEAR_HISTORY = "clear_history"
    EXPORT_HISTORY = "export_history"
    OPEN_BROWSER = "open_browser"
    CLOSE_BROWSER = "close_browser"
    OPEN_WEBSITE = "open_website"
    SEARCH_WEB = "search_web"
    OPEN_NEW_TAB = "open_new_tab"
    CLOSE_TAB = "close_tab"
    SWITCH_TAB = "switch_tab"
    LIST_TABS = "list_tabs"
    REFRESH_PAGE = "refresh_page"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"
    GET_PAGE_INFORMATION = "get_page_information"
    FIND_TEXT_ON_PAGE = "find_text_on_page"
    OPEN_BOOKMARK = "open_bookmark"
    SAVE_BOOKMARK = "save_bookmark"


class ActionStatus(StrEnum):
    """Lifecycle states for an action proposal or its later execution."""

    PENDING = "pending"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"
    PARTIALLY_COMPLETED = "partially_completed"


class RiskLevel(StrEnum):
    """Risk levels from reversible operations through prohibited ones."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionDecision(StrEnum):
    """A future safety policy's authorization decision."""

    ALLOW = "allow"
    REQUIRE_CONFIRMATION = "require_confirmation"
    DENY = "deny"


class ConfirmationStatus(StrEnum):
    """The current state of a user-confirmation requirement."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class EntityType(StrEnum):
    """Kinds of values a future command-understanding layer may extract."""

    APPLICATION = "application"
    FILE = "file"
    FOLDER = "folder"
    PATH = "path"
    FILE_NAME = "file_name"
    FOLDER_NAME = "folder_name"
    FILE_EXTENSION = "file_extension"
    LOCATION = "location"
    TEXT_CONTENT = "text_content"
    SEARCH_QUERY = "search_query"
    BOOLEAN = "boolean"
    NUMBER = "number"
    DURATION = "duration"
    URL = "url"
    TAB = "tab"
    BOOKMARK = "bookmark"
    WEB_QUERY = "web_query"
    UNKNOWN = "unknown"


class ErrorCategory(StrEnum):
    """Categories for serializable error records."""

    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    PARSING = "parsing"
    PERMISSION = "permission"
    SAFETY = "safety"
    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    EXECUTION = "execution"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNSUPPORTED = "unsupported"
    INTERNAL = "internal"


class CommandSource(StrEnum):
    """Future sources of a command without embedding source-specific objects."""

    TEXT = "text"
    VOICE = "voice"
    SYSTEM = "system"
    SCHEDULED = "scheduled"
