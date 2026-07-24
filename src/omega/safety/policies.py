"""Ordered, typed policies for Omega's default-deny safety engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PureWindowsPath
from typing import ClassVar, Protocol, cast

from omega.models import IntentType, PermissionDecision, RiskLevel
from omega.safety.models import SafetyContext
from omega.safety.protected_resources import ProtectedResourceResult


class PolicyDisposition(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    ALLOW = "allow"
    REQUIRE_CONFIRMATION = "require_confirmation"
    DENY = "deny"


@dataclass(frozen=True)
class PolicyResult:
    policy_id: str
    disposition: PolicyDisposition
    reason_code: str
    reason: str
    user_message: str


class SafetyPolicy(Protocol):
    policy_id: str
    priority: int

    def evaluate(
        self,
        context: SafetyContext,
        *,
        risk_level: RiskLevel,
        protected: ProtectedResourceResult,
    ) -> PolicyResult: ...


class _BasePolicy:
    policy_id: ClassVar[str]
    priority: ClassVar[int]

    @classmethod
    def result(
        cls,
        disposition: PolicyDisposition,
        reason_code: str,
        reason: str,
        user_message: str,
    ) -> PolicyResult:
        return PolicyResult(
            cls.policy_id,
            disposition,
            reason_code,
            reason,
            user_message,
        )

    @classmethod
    def na(cls) -> PolicyResult:
        return cls.result(
            PolicyDisposition.NOT_APPLICABLE,
            "POLICY_NOT_APPLICABLE",
            "Policy did not apply.",
            "",
        )


class UnknownActionDenyPolicy(_BasePolicy):
    policy_id = "SAFETY-UNKNOWN-DENY-001"
    priority = 20

    def evaluate(
        self,
        context: SafetyContext,
        **_: object,
    ) -> PolicyResult:
        if context.action.intent is IntentType.UNKNOWN:
            return self.result(
                PolicyDisposition.DENY,
                "UNKNOWN_ACTION",
                "Unknown actions are not executable.",
                "Omega does not have permission to perform that operation.",
            )

        return self.na()


class CriticalRiskDenyPolicy(_BasePolicy):
    policy_id = "SAFETY-CRITICAL-DENY-001"
    priority = 30

    _RECOVERABLE_DELETION_INTENTS = frozenset(
        {
            IntentType.DELETE_FILE,
            IntentType.DELETE_FOLDER,
            IntentType.SIGN_OUT_USER,
            IntentType.RESTART_COMPUTER,
            IntentType.SHUT_DOWN_COMPUTER,
        }
    )

    def evaluate(
        self,
        context: SafetyContext,
        *,
        risk_level: RiskLevel,
        **_: object,
    ) -> PolicyResult:
        if (
            risk_level is RiskLevel.CRITICAL
            and context.action.intent not in self._RECOVERABLE_DELETION_INTENTS
        ):
            return self.result(
                PolicyDisposition.DENY,
                "CRITICAL_RISK_DENIED",
                "Critical-risk operations are prohibited.",
                "Omega does not have permission to perform that critical " "operation.",
            )

        return self.na()


class ProtectedResourceDenyPolicy(_BasePolicy):
    policy_id = "SAFETY-PROTECTED-PATH-001"
    priority = 40

    def evaluate(
        self,
        context: SafetyContext,
        *,
        protected: ProtectedResourceResult,
        **_: object,
    ) -> PolicyResult:
        if protected.denied:
            return PolicyResult(
                protected.policy_id,
                PolicyDisposition.DENY,
                protected.reason_code,
                protected.reason_code.replace("_", " ").title(),
                protected.user_message,
            )

        return self.na()


class ArbitraryShellDenyPolicy(_BasePolicy):
    policy_id = "SAFETY-SHELL-DENY-001"
    priority = 31

    _PREFIXES = (
        "run ",
        "execute ",
        "launch command ",
    )

    def evaluate(
        self,
        context: SafetyContext,
        **_: object,
    ) -> PolicyResult:
        text = context.command.original_text.strip().casefold()

        if (
            text.startswith(self._PREFIXES)
            or context.additional_context.get("shell_like") is True
        ):
            return self.result(
                PolicyDisposition.DENY,
                "ARBITRARY_SHELL_DENIED",
                "Arbitrary shell execution is outside Omega's capabilities.",
                "Omega does not execute arbitrary shell commands.",
            )

        return self.na()


class RecoverableDeletionPolicy(_BasePolicy):
    """Require confirmation for Recycle Bin deletion.

    This policy authorizes only the typed delete intents. The domain manager
    must still execute WindowsRecycleBinService rather than permanent
    filesystem deletion.
    """

    policy_id = "SAFETY-RECOVERABLE-DELETE-001"
    priority = 32

    def evaluate(
        self,
        context: SafetyContext,
        **_: object,
    ) -> PolicyResult:
        if context.action.intent is IntentType.DELETE_FILE:
            return self.result(
                PolicyDisposition.REQUIRE_CONFIRMATION,
                "FILE_RECYCLE_CONFIRMATION",
                "Moving a file to the Recycle Bin requires confirmation.",
                "Moving this file to the Recycle Bin requires exact " "confirmation.",
            )

        if context.action.intent is IntentType.DELETE_FOLDER:
            return self.result(
                PolicyDisposition.REQUIRE_CONFIRMATION,
                "FOLDER_RECYCLE_CONFIRMATION",
                "Moving a folder to the Recycle Bin requires confirmation.",
                "Moving this folder to the Recycle Bin requires exact " "confirmation.",
            )

        return self.na()


class UnsafeExtensionDenyPolicy(_BasePolicy):
    policy_id = "SAFETY-UNSAFE-EXTENSION-001"
    priority = 45

    _BLOCKED = frozenset(
        {
            ".exe",
            ".dll",
            ".bat",
            ".cmd",
            ".ps1",
            ".vbs",
            ".scr",
            ".msi",
            ".reg",
            ".sys",
            ".com",
            ".lnk",
            ".url",
        }
    )

    _DELETION_INTENTS = frozenset(
        {
            IntentType.DELETE_FILE,
            IntentType.DELETE_FOLDER,
        }
    )

    def evaluate(
        self,
        context: SafetyContext,
        **_: object,
    ) -> PolicyResult:
        if context.action.intent in self._DELETION_INTENTS:
            return self.na()

        for key, value in context.action.parameters.items():
            if not isinstance(value, str) or "file" not in key and "name" not in key:
                continue

            if Path(PureWindowsPath(value).name).suffix.casefold() in self._BLOCKED:
                return self.result(
                    PolicyDisposition.DENY,
                    "UNSAFE_EXTENSION_DENIED",
                    "Executable and script-like extensions are prohibited.",
                    "Omega does not create, modify, open, or execute "
                    "command-script files.",
                )

        return self.na()


class DestinationConflictPolicy(_BasePolicy):
    policy_id = "SAFETY-DESTINATION-CONFLICT-001"
    priority = 50

    def evaluate(
        self,
        context: SafetyContext,
        **_: object,
    ) -> PolicyResult:
        if context.additional_context.get("destination_conflict") is True:
            return self.result(
                PolicyDisposition.DENY,
                "DESTINATION_CONFLICT",
                "Destination replacement and folder merging are disabled.",
                "That destination already exists, and Omega does not replace " "it.",
            )

        return self.na()


class AbsolutePathDenyPolicy(_BasePolicy):
    policy_id = "SAFETY-ABSOLUTE-PATH-001"
    priority = 41

    def evaluate(
        self,
        context: SafetyContext,
        *,
        protected: ProtectedResourceResult,
        **_: object,
    ) -> PolicyResult:
        if protected.reason_code in {
            "ABSOLUTE_PATH_REJECTED",
            "SPECIAL_PATH_REJECTED",
            "ALTERNATE_STREAM_REJECTED",
            "PATH_TRAVERSAL_REJECTED",
            "PATH_EXPANSION_REJECTED",
        }:
            return PolicyResult(
                self.policy_id,
                PolicyDisposition.DENY,
                protected.reason_code,
                "The requested path is outside approved logical roots.",
                protected.user_message,
            )

        return self.na()


class SymlinkAndJunctionDenyPolicy(_BasePolicy):
    policy_id = "SAFETY-LINK-DENY-001"
    priority = 42

    def evaluate(
        self,
        context: SafetyContext,
        *,
        protected: ProtectedResourceResult,
        **_: object,
    ) -> PolicyResult:
        if protected.reason_code == "LINKED_PATH_REJECTED":
            return PolicyResult(
                self.policy_id,
                PolicyDisposition.DENY,
                protected.reason_code,
                "Linked path rejected.",
                protected.user_message,
            )

        return self.na()


class _IntentPolicy(_BasePolicy):
    intents: ClassVar[frozenset[IntentType]]
    disposition: ClassVar[PolicyDisposition]
    reason_code: ClassVar[str]
    message: ClassVar[str]

    def evaluate(
        self,
        context: SafetyContext,
        **_: object,
    ) -> PolicyResult:
        if context.action.intent not in self.intents:
            return self.na()

        return self.result(
            self.disposition,
            self.reason_code,
            "The action matched an explicit Omega operation policy.",
            self.message,
        )


class ApplicationOpenPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-APP-OPEN-001", 80
    intents = frozenset({IntentType.OPEN_APPLICATION})
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "REGISTERED_APPLICATION_ALLOWED",
        "Registered application launch is allowed after validation.",
    )


class ApplicationStatusPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-APP-STATUS-001", 80
    intents = frozenset({IntentType.CHECK_APPLICATION_STATUS})
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "APPLICATION_STATUS_ALLOWED",
        "Registered application status inspection is allowed.",
    )


class ApplicationClosePolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-APP-CLOSE-001", 70
    intents = frozenset({IntentType.CLOSE_APPLICATION})
    disposition, reason_code, message = (
        PolicyDisposition.REQUIRE_CONFIRMATION,
        "APPLICATION_CLOSE_CONFIRMATION",
        "Closing an application requires exact confirmation.",
    )


class FileReadPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FILE-READ-001", 80
    intents = frozenset(
        {
            IntentType.READ_FILE,
            IntentType.OPEN_FILE,
            IntentType.SEARCH_FILE,
            IntentType.CHECK_FILE_EXISTENCE,
            IntentType.GET_FILE_INFORMATION,
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "FILE_INSPECTION_ALLOWED",
        "Validated file inspection is allowed.",
    )


class FileCreatePolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FILE-CREATE-001", 80
    intents = frozenset({IntentType.CREATE_FILE})
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "FILE_CREATE_ALLOWED",
        "Validated file creation is allowed.",
    )


class FileWritePolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FILE-WRITE-001", 70
    intents = frozenset({IntentType.WRITE_FILE})
    disposition, reason_code, message = (
        PolicyDisposition.REQUIRE_CONFIRMATION,
        "FILE_OVERWRITE_CONFIRMATION",
        "Replacing file content requires exact confirmation.",
    )

    def evaluate(
        self,
        context: SafetyContext,
        **_: object,
    ) -> PolicyResult:
        if context.action.intent is not IntentType.WRITE_FILE:
            return self.na()

        if not context.additional_context.get(
            "target_has_content",
            context.target_exists,
        ):
            return self.result(
                PolicyDisposition.ALLOW,
                "FILE_WRITE_NEW_ALLOWED",
                "Writing a new validated text file does not replace data.",
                "Writing the new text file is allowed after validation.",
            )

        return super().evaluate(context)


class FileAppendPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FILE-APPEND-001", 80
    intents = frozenset({IntentType.APPEND_FILE})
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "FILE_APPEND_ALLOWED",
        "Bounded text append is allowed.",
    )


class FileRenamePolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FILE-RENAME-001", 80
    intents = frozenset({IntentType.RENAME_FILE})
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "FILE_RENAME_ALLOWED",
        "Non-conflicting file rename is allowed.",
    )


class FileCopyPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FILE-COPY-001", 80
    intents = frozenset({IntentType.COPY_FILE})
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "FILE_COPY_ALLOWED",
        "Non-conflicting file copy is allowed.",
    )


class FileMovePolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FILE-MOVE-001", 70
    intents = frozenset({IntentType.MOVE_FILE})
    disposition, reason_code, message = (
        PolicyDisposition.REQUIRE_CONFIRMATION,
        "FILE_MOVE_CONFIRMATION",
        "Moving a file requires exact confirmation.",
    )


class FolderInspectPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FOLDER-INSPECT-001", 80
    intents = frozenset(
        {
            IntentType.OPEN_FOLDER,
            IntentType.LIST_FOLDER,
            IntentType.SEARCH_FOLDER,
            IntentType.CHECK_FOLDER_EXISTENCE,
            IntentType.GET_FOLDER_INFORMATION,
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "FOLDER_INSPECTION_ALLOWED",
        "Validated folder inspection is allowed.",
    )


class FolderCreatePolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FOLDER-CREATE-001", 80
    intents = frozenset({IntentType.CREATE_FOLDER})
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "FOLDER_CREATE_ALLOWED",
        "Validated folder creation is allowed.",
    )


class FolderRenamePolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FOLDER-RENAME-001", 80
    intents = frozenset({IntentType.RENAME_FOLDER})
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "FOLDER_RENAME_ALLOWED",
        "Non-conflicting folder rename is allowed.",
    )


class FolderCopyPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FOLDER-COPY-001", 80
    intents = frozenset({IntentType.COPY_FOLDER})
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "FOLDER_COPY_ALLOWED",
        "Bounded non-conflicting folder copy is allowed.",
    )


class FolderMovePolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-FOLDER-MOVE-001", 70
    intents = frozenset({IntentType.MOVE_FOLDER})
    disposition, reason_code, message = (
        PolicyDisposition.REQUIRE_CONFIRMATION,
        "FOLDER_MOVE_CONFIRMATION",
        "Moving a folder requires exact confirmation.",
    )


class HistoryReadPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-HISTORY-READ-001", 80
    intents = frozenset({IntentType.SHOW_HISTORY})
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "HISTORY_READ_ALLOWED",
        "Bounded local history inspection is allowed.",
    )


class HistoryExportPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-HISTORY-EXPORT-001", 80
    intents = frozenset({IntentType.EXPORT_HISTORY})
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "HISTORY_EXPORT_ALLOWED",
        "Bounded JSON history export is allowed.",
    )


class HistoryMutationPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-HISTORY-MUTATION-001", 70
    intents = frozenset({IntentType.CLEAR_HISTORY, IntentType.UNDO_LAST_ACTION})
    disposition, reason_code, message = (
        PolicyDisposition.REQUIRE_CONFIRMATION,
        "HISTORY_MUTATION_CONFIRMATION",
        "History cleanup and undo require exact confirmation.",
    )


class BrowserInspectPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-BROWSER-INSPECT-001", 80
    intents = frozenset(
        {
            IntentType.CLOSE_TAB,
            IntentType.LIST_TABS,
            IntentType.REFRESH_PAGE,
            IntentType.GO_BACK,
            IntentType.GO_FORWARD,
            IntentType.GET_PAGE_INFORMATION,
            IntentType.FIND_TEXT_ON_PAGE,
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "BROWSER_INSPECTION_ALLOWED",
        "Bounded Omega browser inspection is allowed.",
    )


class BrowserNavigationPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-BROWSER-NAVIGATE-001", 80
    intents = frozenset(
        {
            IntentType.OPEN_BROWSER,
            IntentType.OPEN_WEBSITE,
            IntentType.SEARCH_WEB,
            IntentType.OPEN_NEW_TAB,
            IntentType.SWITCH_TAB,
            IntentType.OPEN_BOOKMARK,
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "VALIDATED_BROWSER_NAVIGATION_ALLOWED",
        "Validated browser navigation is allowed.",
    )


class BrowserMutationPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-BROWSER-MUTATION-001", 70
    intents = frozenset({IntentType.CLOSE_BROWSER, IntentType.SAVE_BOOKMARK})
    disposition, reason_code, message = (
        PolicyDisposition.REQUIRE_CONFIRMATION,
        "BROWSER_MUTATION_CONFIRMATION",
        "Closing the controlled browser or saving a bookmark requires confirmation.",
    )


class SystemReadPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-SYSTEM-READ-001", 80
    intents = frozenset(
        {
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
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "BOUNDED_SYSTEM_OPERATION_ALLOWED",
        "The bounded system operation is allowed.",
    )


class SystemControlPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-SYSTEM-CONTROL-001", 80
    intents = frozenset(
        {
            IntentType.SET_VOLUME,
            IntentType.INCREASE_VOLUME,
            IntentType.DECREASE_VOLUME,
            IntentType.MUTE_VOLUME,
            IntentType.UNMUTE_VOLUME,
            IntentType.SET_BRIGHTNESS,
            IntentType.INCREASE_BRIGHTNESS,
            IntentType.DECREASE_BRIGHTNESS,
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "BOUNDED_DEVICE_CONTROL_ALLOWED",
        "The bounded device control is allowed.",
    )


class PowerActionPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-POWER-CONFIRM-001", 70
    intents = frozenset(
        {
            IntentType.LOCK_COMPUTER,
            IntentType.SLEEP_COMPUTER,
            IntentType.HIBERNATE_COMPUTER,
            IntentType.SIGN_OUT_USER,
            IntentType.RESTART_COMPUTER,
            IntentType.SHUT_DOWN_COMPUTER,
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.REQUIRE_CONFIRMATION,
        "POWER_ACTION_CONFIRMATION",
        "Windows power actions require exact scoped confirmation.",
    )


class SchedulingPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-SCHEDULING-001", 80
    intents = frozenset(
        {
            IntentType.CREATE_REMINDER,
            IntentType.CREATE_RECURRING_REMINDER,
            IntentType.LIST_REMINDERS,
            IntentType.SHOW_REMINDER,
            IntentType.UPDATE_REMINDER,
            IntentType.CANCEL_REMINDER,
            IntentType.COMPLETE_REMINDER,
            IntentType.SNOOZE_REMINDER,
            IntentType.CREATE_ALARM,
            IntentType.CREATE_RECURRING_ALARM,
            IntentType.LIST_ALARMS,
            IntentType.SHOW_ALARM,
            IntentType.UPDATE_ALARM,
            IntentType.CANCEL_ALARM,
            IntentType.DISMISS_ALARM,
            IntentType.SNOOZE_ALARM,
            IntentType.START_TIMER,
            IntentType.PAUSE_TIMER,
            IntentType.RESUME_TIMER,
            IntentType.CANCEL_TIMER,
            IntentType.SHOW_TIMER,
            IntentType.LIST_TIMERS,
            IntentType.LIST_SCHEDULED_ITEMS,
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "LOCAL_SCHEDULING_ALLOWED",
        "Validated local scheduling is allowed.",
    )


class ProductivityPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-PRODUCTIVITY-001", 80
    intents = frozenset(
        {
            IntentType.CREATE_NOTE,
            IntentType.LIST_NOTES,
            IntentType.SHOW_NOTE,
            IntentType.UPDATE_NOTE,
            IntentType.APPEND_NOTE,
            IntentType.SEARCH_NOTES,
            IntentType.PIN_NOTE,
            IntentType.UNPIN_NOTE,
            IntentType.ARCHIVE_NOTE,
            IntentType.RESTORE_NOTE,
            IntentType.TAG_NOTE,
            IntentType.UNTAG_NOTE,
            IntentType.EXPORT_NOTES,
            IntentType.IMPORT_NOTES,
            IntentType.CREATE_TASK_LIST,
            IntentType.LIST_TASK_LISTS,
            IntentType.SHOW_TASK_LIST,
            IntentType.UPDATE_TASK_LIST,
            IntentType.ARCHIVE_TASK_LIST,
            IntentType.RESTORE_TASK_LIST,
            IntentType.CREATE_TASK,
            IntentType.LIST_TASKS,
            IntentType.SHOW_TASK,
            IntentType.UPDATE_TASK,
            IntentType.COMPLETE_TASK,
            IntentType.REOPEN_TASK,
            IntentType.CANCEL_TASK,
            IntentType.ARCHIVE_TASK,
            IntentType.RESTORE_TASK,
            IntentType.SET_TASK_PRIORITY,
            IntentType.SET_TASK_DEADLINE,
            IntentType.REMOVE_TASK_DEADLINE,
            IntentType.MOVE_TASK,
            IntentType.TAG_TASK,
            IntentType.UNTAG_TASK,
            IntentType.SEARCH_TASKS,
            IntentType.SHOW_DUE_TASKS,
            IntentType.SHOW_OVERDUE_TASKS,
            IntentType.LINK_TASK_REMINDER,
            IntentType.UNLINK_TASK_REMINDER,
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "LOCAL_PRODUCTIVITY_ALLOWED",
        "Validated local productivity operations are allowed.",
    )


class ProductivityDeletionPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-PRODUCTIVITY-DELETE-001", 70
    intents = frozenset(
        {
            IntentType.DELETE_NOTE,
            IntentType.DELETE_TASK,
            IntentType.DELETE_TASK_LIST,
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.REQUIRE_CONFIRMATION,
        "PRODUCTIVITY_DELETE_CONFIRMATION",
        "Deleting local productivity data requires exact scoped confirmation.",
    )


class KnowledgePolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-KNOWLEDGE-001", 80
    intents = frozenset(
        {
            IntentType.CREATE_KNOWLEDGE_COLLECTION,
            IntentType.LIST_KNOWLEDGE_COLLECTIONS,
            IntentType.SHOW_KNOWLEDGE_COLLECTION,
            IntentType.UPDATE_KNOWLEDGE_COLLECTION,
            IntentType.ARCHIVE_KNOWLEDGE_COLLECTION,
            IntentType.RESTORE_KNOWLEDGE_COLLECTION,
            IntentType.IMPORT_KNOWLEDGE_DOCUMENT,
            IntentType.LIST_KNOWLEDGE_DOCUMENTS,
            IntentType.SHOW_KNOWLEDGE_DOCUMENT,
            IntentType.MOVE_KNOWLEDGE_DOCUMENT,
            IntentType.REINDEX_KNOWLEDGE_DOCUMENT,
            IntentType.SEARCH_KNOWLEDGE,
            IntentType.ASK_KNOWLEDGE,
            IntentType.SHOW_KNOWLEDGE_SOURCES,
            IntentType.EXPORT_KNOWLEDGE_RESULTS,
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.ALLOW,
        "LOCAL_KNOWLEDGE_ALLOWED",
        "Validated local-only knowledge operations are allowed.",
    )


class KnowledgeDeletionPolicy(_IntentPolicy):
    policy_id, priority = "SAFETY-KNOWLEDGE-DELETE-001", 70
    intents = frozenset(
        {
            IntentType.REMOVE_KNOWLEDGE_DOCUMENT,
            IntentType.DELETE_KNOWLEDGE_COLLECTION,
        }
    )
    disposition, reason_code, message = (
        PolicyDisposition.REQUIRE_CONFIRMATION,
        "KNOWLEDGE_REMOVAL_CONFIRMATION",
        "Removing indexed knowledge requires exact scoped confirmation.",
    )


DEFAULT_POLICIES = cast(
    tuple[SafetyPolicy, ...],
    (
        UnknownActionDenyPolicy(),
        CriticalRiskDenyPolicy(),
        ArbitraryShellDenyPolicy(),
        RecoverableDeletionPolicy(),
        AbsolutePathDenyPolicy(),
        SymlinkAndJunctionDenyPolicy(),
        ProtectedResourceDenyPolicy(),
        UnsafeExtensionDenyPolicy(),
        DestinationConflictPolicy(),
        ApplicationClosePolicy(),
        FileWritePolicy(),
        FileMovePolicy(),
        FolderMovePolicy(),
        HistoryMutationPolicy(),
        BrowserMutationPolicy(),
        PowerActionPolicy(),
        ProductivityDeletionPolicy(),
        KnowledgeDeletionPolicy(),
        ApplicationOpenPolicy(),
        ApplicationStatusPolicy(),
        FileReadPolicy(),
        FileCreatePolicy(),
        FileAppendPolicy(),
        FileRenamePolicy(),
        FileCopyPolicy(),
        FolderInspectPolicy(),
        FolderCreatePolicy(),
        FolderRenamePolicy(),
        FolderCopyPolicy(),
        HistoryReadPolicy(),
        HistoryExportPolicy(),
        BrowserInspectPolicy(),
        BrowserNavigationPolicy(),
        SystemReadPolicy(),
        SystemControlPolicy(),
        SchedulingPolicy(),
        ProductivityPolicy(),
        KnowledgePolicy(),
    ),
)


def disposition_decision(
    value: PolicyDisposition,
) -> PermissionDecision | None:
    if value is PolicyDisposition.ALLOW:
        return PermissionDecision.ALLOW

    if value is PolicyDisposition.REQUIRE_CONFIRMATION:
        return PermissionDecision.REQUIRE_CONFIRMATION

    if value is PolicyDisposition.DENY:
        return PermissionDecision.DENY

    return None
