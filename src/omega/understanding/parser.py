"""Orchestration for Omega's deterministic Phase 3 understanding pipeline."""

from __future__ import annotations

import re
from uuid import UUID

from omega.models import CommandEntity, CommandSource, IntentType, UserCommand
from omega.understanding.aliases import ApplicationAliasRegistry
from omega.understanding.entities import RuleBasedEntityExtractor
from omega.understanding.intents import RuleBasedIntentDetector
from omega.understanding.normalizer import CommandNormalizer
from omega.understanding.result import CommandParseResult

_DANGEROUS = (
    "format the c drive",
    "disable windows defender",
    "system32",
    "powershell script",
    "execute rm",
    "execute this powershell",
    "javascript:",
    "enter my password",
    "enter password",
    "submit payment",
    "buy this",
    "accept the terms",
    "bypass captcha",
    "download executable",
    "install extension",
    "developer console",
)

_BROWSER_NO_PARAMETER = frozenset(
    {
        IntentType.OPEN_BROWSER,
        IntentType.CLOSE_BROWSER,
        IntentType.OPEN_NEW_TAB,
        IntentType.LIST_TABS,
        IntentType.REFRESH_PAGE,
        IntentType.GO_BACK,
        IntentType.GO_FORWARD,
        IntentType.GET_PAGE_INFORMATION,
    }
)

_SYSTEM_NO_PARAMETER = frozenset(
    {
        IntentType.GET_SYSTEM_INFORMATION,
        IntentType.GET_CPU_USAGE,
        IntentType.GET_MEMORY_USAGE,
        IntentType.GET_DISK_USAGE,
        IntentType.GET_BATTERY_STATUS,
        IntentType.GET_NETWORK_STATUS,
        IntentType.LIST_PROCESSES,
        IntentType.GET_VOLUME,
        IntentType.MUTE_VOLUME,
        IntentType.UNMUTE_VOLUME,
        IntentType.GET_BRIGHTNESS,
        IntentType.LOCK_COMPUTER,
        IntentType.SLEEP_COMPUTER,
        IntentType.HIBERNATE_COMPUTER,
        IntentType.SIGN_OUT_USER,
        IntentType.RESTART_COMPUTER,
        IntentType.SHUT_DOWN_COMPUTER,
        IntentType.CANCEL_POWER_ACTION,
    }
)
_SCHEDULING_NO_PARAMETER = frozenset(
    {
        IntentType.LIST_REMINDERS,
        IntentType.LIST_ALARMS,
        IntentType.LIST_TIMERS,
        IntentType.LIST_SCHEDULED_ITEMS,
    }
)


class CommandParser:
    """Create structured command data and clarifications without side effects."""

    def __init__(self, aliases: ApplicationAliasRegistry | None = None) -> None:
        self.aliases = aliases or ApplicationAliasRegistry.from_file()
        self.normalizer = CommandNormalizer()
        self.detector = RuleBasedIntentDetector(self.aliases)
        self.extractor = RuleBasedEntityExtractor(self.aliases)

    def parse(
        self,
        original_text: str,
        session_id: UUID | None = None,
        *,
        source: CommandSource = CommandSource.TEXT,
    ) -> CommandParseResult:
        normalized = self.normalizer.normalize(original_text)
        if (
            self._multiple_actions(normalized)
            or " and " in self._outside_quotes(normalized)
            and self._action_verb_count(self._outside_quotes(normalized)) > 1
        ):
            command = UserCommand(
                original_text,
                normalized_text=normalized,
                confidence=0.3,
                source=source,
                session_id=session_id,
            )
            return CommandParseResult(
                command,
                False,
                True,
                "Omega currently understands one action at a time. "
                "Please give one command first.",
                warnings=["multiple_actions"],
            )
        if any(phrase in normalized for phrase in _DANGEROUS):
            command = UserCommand(
                original_text,
                normalized_text=normalized,
                confidence=0.0,
                source=source,
                session_id=session_id,
            )
            return CommandParseResult(
                command,
                False,
                True,
                "I don't understand that command yet.",
                warnings=["unsupported_or_dangerous"],
            )

        intent, pattern = self.detector.detect(normalized)
        entities = self.extractor.extract(original_text.strip().rstrip("?!"), intent)
        ambiguity = self._ambiguity(normalized, intent, entities)
        missing, message = self._missing(intent, entities, normalized)
        matched = intent is not IntentType.UNKNOWN
        clarification = bool(ambiguity or missing)
        confidence = (
            0.0 if not matched else 0.5 if ambiguity else 0.65 if missing else 1.0
        )
        command = UserCommand(
            original_text,
            normalized_text=normalized,
            intent=intent,
            entities=entities,
            confidence=confidence,
            source=source,
            session_id=session_id,
        )
        if ambiguity:
            message = (
                "Do you want to open an application, file, or folder named "
                f"{ambiguity[0]}?"
            )
        return CommandParseResult(
            command, matched, clarification, message, missing, ambiguity, pattern
        )

    @staticmethod
    def _outside_quotes(text: str) -> str:
        return re.sub(r'(["\']).*?\1', "", text)

    @classmethod
    def _multiple_actions(cls, text: str) -> bool:
        outside = cls._outside_quotes(text)
        return " then " in outside and cls._action_verb_count(outside) > 1

    @staticmethod
    def _action_verb_count(text: str) -> int:
        return len(
            re.findall(
                r"\b(?:open|launch|start|run|close|create|make|delete|move|copy|rename|write|append|read|find|search)\b",
                text,
            )
        )

    def _ambiguity(
        self,
        normalized: str,
        intent: IntentType,
        entities: list[CommandEntity],
    ) -> list[str]:
        if intent is IntentType.OPEN_APPLICATION and not self.aliases.resolve(
            normalized
        ):
            target = re.sub(r"^(?:open|launch|start|run)\s*", "", normalized)
            if target and "." not in target and not target.endswith(" folder"):
                return [target]
        return []

    @staticmethod
    def _missing(
        intent: IntentType,
        entities: list[CommandEntity],
        normalized: str,
    ) -> tuple[list[str], str | None]:
        names = {entity.name for entity in entities}
        if (
            intent
            in {
                IntentType.CREATE_REMINDER,
                IntentType.CREATE_ALARM,
                IntentType.CREATE_RECURRING_REMINDER,
                IntentType.CREATE_RECURRING_ALARM,
                IntentType.UPDATE_REMINDER,
                IntentType.UPDATE_ALARM,
            }
            and len(
                re.findall(
                    r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b",
                    normalized,
                )
            )
            > 1
        ):
            return ["date_time"], "Use one unambiguous clock time."
        if (
            intent
            in {
                IntentType.OPEN_APPLICATION,
                IntentType.CLOSE_APPLICATION,
                IntentType.CHECK_APPLICATION_STATUS,
            }
            and "application_name" not in names
        ):
            return ["application_name"], (
                "Which application would you like me to open?"
                if intent is IntentType.OPEN_APPLICATION
                else "Which application do you mean?"
            )
        if intent in _BROWSER_NO_PARAMETER:
            return [], None
        if intent in _SYSTEM_NO_PARAMETER:
            return [], None
        if intent in _SCHEDULING_NO_PARAMETER:
            return [], None
        if intent is IntentType.START_TIMER and "duration_seconds" not in names:
            return ["duration"], "How long should the timer run?"
        if intent in {
            IntentType.CREATE_REMINDER,
            IntentType.CREATE_ALARM,
            IntentType.CREATE_RECURRING_REMINDER,
            IntentType.CREATE_RECURRING_ALARM,
            IntentType.UPDATE_REMINDER,
            IntentType.UPDATE_ALARM,
        } and {"duration_seconds", "clock_time"}.issubset(names):
            return ["date_time"], "Use either a relative duration or a clock time."
        if intent in {
            IntentType.CREATE_REMINDER,
            IntentType.CREATE_ALARM,
            IntentType.CREATE_RECURRING_REMINDER,
            IntentType.CREATE_RECURRING_ALARM,
            IntentType.UPDATE_REMINDER,
            IntentType.UPDATE_ALARM,
        } and not names.intersection({"duration_seconds", "clock_time"}):
            return ["date_time"], "When should I schedule it?"
        if (
            intent
            in {
                IntentType.SET_VOLUME,
                IntentType.SET_BRIGHTNESS,
            }
            and "percentage" not in names
        ):
            return ["percentage"], "Which percentage should I use?"
        if intent in {
            IntentType.INCREASE_VOLUME,
            IntentType.DECREASE_VOLUME,
            IntentType.INCREASE_BRIGHTNESS,
            IntentType.DECREASE_BRIGHTNESS,
        }:
            values = [item.value for item in entities if item.name == "percentage"]
            if values and (
                len(values) != 1
                or not isinstance(values[0], int)
                or not 1 <= values[0] <= 50
            ):
                return ["percentage"], "Use one increment between 1 and 50 percent."
            return [], None
        if intent in {
            IntentType.SET_VOLUME,
            IntentType.SET_BRIGHTNESS,
        }:
            values = [item.value for item in entities if item.name == "percentage"]
            if (
                len(values) != 1
                or not isinstance(values[0], int)
                or not 0 <= values[0] <= 100
            ):
                return ["percentage"], "Use one percentage between 0 and 100."
        if intent is IntentType.OPEN_WINDOWS_SETTINGS and "settings_page" not in names:
            return ["settings_page"], "Which allowlisted Windows Settings page?"
        if (
            intent
            in {
                IntentType.SEARCH_PROCESS,
                IntentType.GET_PROCESS_INFORMATION,
            }
            and "process_name" not in names
        ):
            return ["process_name"], "Which process name should I inspect?"
        if intent is IntentType.OPEN_WEBSITE and "url" not in names:
            return ["url"], "Which HTTPS website should I open?"
        if intent is IntentType.SEARCH_WEB and "search_query" not in names:
            return ["search_query"], "What should I search the web for?"
        if (
            intent in {IntentType.CLOSE_TAB, IntentType.SWITCH_TAB}
            and "tab" not in names
        ):
            return ["tab"], "Which tab do you mean?"
        if intent is IntentType.FIND_TEXT_ON_PAGE and "text_content" not in names:
            return ["text_content"], "Which text should I find on the page?"
        if intent in {IntentType.OPEN_BOOKMARK, IntentType.SAVE_BOOKMARK} and (
            "bookmark_name" not in names
        ):
            return ["bookmark_name"], "Which bookmark name should I use?"
        if intent is IntentType.CREATE_FOLDER and "folder_name" not in names:
            return ["folder_name"], "What should I name the folder?"
        if intent in {
            IntentType.OPEN_FOLDER,
            IntentType.LIST_FOLDER,
            IntentType.DELETE_FOLDER,
            IntentType.CHECK_FOLDER_EXISTENCE,
            IntentType.GET_FOLDER_INFORMATION,
        } and not names.intersection({"folder_name", "location"}):
            return ["folder_name"], "Which folder do you mean?"
        if intent is IntentType.CREATE_FILE and "file_name" not in names:
            return ["file_name"], "What should I name the file?"
        if (
            intent
            in {
                IntentType.DELETE_FILE,
                IntentType.READ_FILE,
                IntentType.OPEN_FILE,
                IntentType.CHECK_FILE_EXISTENCE,
                IntentType.GET_FILE_INFORMATION,
            }
            and "file_name" not in names
        ):
            return ["file_name"], "Which file do you mean?"
        if intent in {IntentType.WRITE_FILE, IntentType.APPEND_FILE}:
            missing = [
                name for name in ("text_content", "file_name") if name not in names
            ]
            if missing:
                return missing, "What should I write, and which file should I use?"
        if (
            intent
            in {
                IntentType.MOVE_FILE,
                IntentType.MOVE_FOLDER,
                IntentType.COPY_FILE,
                IntentType.COPY_FOLDER,
            }
            and "destination" not in names
        ):
            return ["destination"], f"Where should I {intent.value.split('_')[0]} it?"
        if (
            intent in {IntentType.RENAME_FILE, IntentType.RENAME_FOLDER}
            and "new_name" not in names
        ):
            return ["new_name"], "What should the new name be?"
        if intent is IntentType.SEARCH_FILE and not names.intersection(
            {"file_name", "search_extension"}
        ):
            return ["search_query"], "Which file name or extension should I search for?"
        if intent is IntentType.SEARCH_FOLDER and "folder_name" not in names:
            return ["folder_name"], "Which folder name should I search for?"
        if (
            intent
            in {
                IntentType.RENAME_FOLDER,
                IntentType.COPY_FOLDER,
                IntentType.MOVE_FOLDER,
            }
            and "source_folder" not in names
        ):
            return ["source_folder"], "Which folder do you mean?"
        if intent is IntentType.UNKNOWN and normalized in {"open", "close", "delete"}:
            return ["target"], "What would you like me to act on?"
        return [], None
