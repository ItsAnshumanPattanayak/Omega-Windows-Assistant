"""Deterministic intent recognition over normalized text."""

from __future__ import annotations

from omega.models import IntentType
from omega.understanding.aliases import ApplicationAliasRegistry
from omega.understanding.patterns import INTENT_PATTERNS


class RuleBasedIntentDetector:
    """Recognize one supported intent using explicitly ordered rules."""

    def __init__(self, aliases: ApplicationAliasRegistry) -> None:
        self.aliases = aliases

    def detect(self, normalized_text: str) -> tuple[IntentType, str | None]:
        for pattern in INTENT_PATTERNS:
            if not pattern.expression.fullmatch(normalized_text):
                continue
            intent = pattern.intent
            if pattern.name == "open":
                if (
                    " folder" in normalized_text
                    or normalized_text.startswith("open the ")
                    and normalized_text.endswith(" folder")
                    or _opens_logical_location(normalized_text)
                ):
                    intent = IntentType.OPEN_FOLDER
                elif re_has_extension(normalized_text):
                    intent = IntentType.OPEN_FILE
            elif pattern.name == "rename":
                intent = (
                    IntentType.RENAME_FILE
                    if re_has_extension(normalized_text.split(" to ", 1)[0])
                    else IntentType.RENAME_FOLDER
                )
            elif pattern.name == "copy":
                intent = (
                    IntentType.COPY_FILE
                    if re_has_extension(normalized_text.split(" to ", 1)[0])
                    else IntentType.COPY_FOLDER
                )
            elif pattern.name == "move":
                intent = (
                    IntentType.MOVE_FILE
                    if re_has_extension(normalized_text.split(" to ", 1)[0])
                    else IntentType.MOVE_FOLDER
                )
            elif pattern.name == "delete":
                intent = (
                    IntentType.DELETE_FOLDER
                    if " folder" in normalized_text
                    else IntentType.DELETE_FILE
                )
            elif pattern.name == "file_exists" and (
                " folder" in normalized_text
                or " directory" in normalized_text
                or not re_has_extension(normalized_text)
            ):
                intent = IntentType.CHECK_FOLDER_EXISTENCE
            elif pattern.name == "file_information" and (
                " folder" in normalized_text
                or " directory" in normalized_text
                or not re_has_extension(normalized_text)
            ):
                intent = IntentType.GET_FOLDER_INFORMATION
            return intent, pattern.name
        return IntentType.UNKNOWN, None


def re_has_extension(text: str) -> bool:
    import re

    return re.search(r"\.[a-z0-9]{1,10}(?:\b|$)", text) is not None


def _opens_logical_location(text: str) -> bool:
    import re

    locations = (
        "desktop|documents|downloads|pictures|music|videos|home|"
        "current directory|current folder|project directory"
    )
    return re.fullmatch(rf"open (?:the )?(?:{locations})(?:[\\/].+)?", text) is not None
