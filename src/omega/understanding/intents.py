"""Deterministic intent recognition over normalized text."""

from __future__ import annotations

import hashlib
import re

from omega.models import IntentType
from omega.performance.cache import BoundedLruCache
from omega.understanding.aliases import ApplicationAliasRegistry
from omega.understanding.patterns import INTENT_PATTERNS

_EXTENSION = re.compile(r"\.[a-z0-9]{1,10}(?:\b|$)")
_LOGICAL_LOCATION = re.compile(
    r"open (?:the )?(?:desktop|documents|downloads|pictures|music|videos|home|"
    r"current directory|current folder|project directory)(?:[\\/].+)?"
)


class RuleBasedIntentDetector:
    """Recognize one supported intent using explicitly ordered rules."""

    def __init__(
        self, aliases: ApplicationAliasRegistry, *, cache_size: int = 256
    ) -> None:
        self.aliases = aliases
        self._cache: BoundedLruCache[str, tuple[IntentType, str | None]] = (
            BoundedLruCache(cache_size)
        )

    def detect(self, normalized_text: str) -> tuple[IntentType, str | None]:
        key = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
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
            result: tuple[IntentType, str | None] = (intent, pattern.name)
            self._cache.put(key, result)
            return result
        unknown_result = (IntentType.UNKNOWN, None)
        self._cache.put(key, unknown_result)
        return unknown_result

    @property
    def cache_size(self) -> int:
        return self._cache.statistics().size


def re_has_extension(text: str) -> bool:
    return _EXTENSION.search(text) is not None


def _opens_logical_location(text: str) -> bool:
    return _LOGICAL_LOCATION.fullmatch(text) is not None
