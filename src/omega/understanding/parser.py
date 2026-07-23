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
