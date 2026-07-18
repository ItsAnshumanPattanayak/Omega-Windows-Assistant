"""Deterministic extraction of canonical Phase 1 command entities."""

from __future__ import annotations

import re

from omega.models import CommandEntity, EntityType, IntentType
from omega.understanding.aliases import ApplicationAliasRegistry

EXTENSIONS = {
    "text": ".txt",
    "markdown": ".md",
    "json": ".json",
    "csv": ".csv",
    "python": ".py",
    "html": ".html",
    "css": ".css",
    "javascript": ".js",
    "yaml": ".yaml",
}
LOCATIONS = {
    "desktop": "desktop",
    "my desktop": "desktop",
    "documents": "documents",
    "my documents": "documents",
    "downloads": "downloads",
    "my downloads": "downloads",
    "pictures": "pictures",
    "my pictures": "pictures",
    "music": "music",
    "my music": "music",
    "videos": "videos",
    "my videos": "videos",
    "home": "home",
    "home folder": "home",
    "user folder": "home",
    "current directory": "current_directory",
    "current folder": "current_directory",
    "project directory": "current_directory",
}
_LOCATION_EXPRESSION = (
    r"my desktop|desktop|my documents|documents|my downloads|downloads|"
    r"my pictures|pictures|my music|music|my videos|videos|home folder|"
    r"user folder|home|current directory|current folder|project directory"
)


def _entity(entity_type: EntityType, name: str, value: str, raw: str) -> CommandEntity:
    return CommandEntity(entity_type, value, raw_value=raw, name=name, confidence=1.0)


def _location_value(raw: str) -> str:
    return LOCATIONS[" ".join(raw.casefold().split())]


class RuleBasedEntityExtractor:
    """Extract known applications and tightly scoped Phase 5 file values."""

    def __init__(self, aliases: ApplicationAliasRegistry) -> None:
        self.aliases = aliases

    def extract(self, original: str, intent: IntentType) -> list[CommandEntity]:
        entities: list[CommandEntity] = []
        self._application(original, intent, entities)
        self._file_type(original, entities)
        if intent in {
            IntentType.CREATE_FILE,
            IntentType.READ_FILE,
            IntentType.WRITE_FILE,
            IntentType.APPEND_FILE,
            IntentType.OPEN_FILE,
            IntentType.DELETE_FILE,
            IntentType.SEARCH_FILE,
            IntentType.CHECK_FILE_EXISTENCE,
            IntentType.GET_FILE_INFORMATION,
        }:
            self._single_file(original, intent, entities)
        elif intent is IntentType.RENAME_FILE:
            self._rename(original, entities)
        elif intent in {IntentType.COPY_FILE, IntentType.MOVE_FILE}:
            self._transfer(original, entities)
        elif intent is IntentType.CREATE_FOLDER:
            self._folder(original, entities)
        return entities

    def _application(
        self, original: str, intent: IntentType, entities: list[CommandEntity]
    ) -> None:
        alias = self.aliases.resolve(original)
        if alias is None or intent not in {
            IntentType.OPEN_APPLICATION,
            IntentType.CLOSE_APPLICATION,
            IntentType.CHECK_APPLICATION_STATUS,
        }:
            return
        canonical, matched = alias
        raw = re.search(re.escape(matched), original, re.IGNORECASE)
        entities.append(
            _entity(
                EntityType.APPLICATION,
                "application_name",
                canonical,
                raw.group(0) if raw else matched,
            )
        )

    @staticmethod
    def _file_type(original: str, entities: list[CommandEntity]) -> None:
        match = re.search(
            r"\b(text|markdown|json|csv|python|html|css|javascript|yaml) file\b",
            original,
            re.IGNORECASE,
        )
        if match:
            entities.append(
                _entity(
                    EntityType.FILE_EXTENSION,
                    "file_extension",
                    EXTENSIONS[match.group(1).casefold()],
                    match.group(0),
                )
            )

    def _single_file(
        self, original: str, intent: IntentType, entities: list[CommandEntity]
    ) -> None:
        working = original.strip()
        location_match = re.search(
            rf"\s+(?:on|in|from)\s+({_LOCATION_EXPRESSION})" r"(?:[\\/](.+))?$",
            working,
            re.IGNORECASE,
        )
        if location_match:
            entities.append(
                _entity(
                    EntityType.LOCATION,
                    "location",
                    _location_value(location_match.group(1)),
                    location_match.group(1),
                )
            )
            if location_match.group(2):
                entities.append(
                    _entity(
                        EntityType.PATH,
                        "relative_subpath",
                        location_match.group(2).strip(),
                        location_match.group(2).strip(),
                    )
                )
            working = working[: location_match.start()].rstrip()

        quoted = re.search(r'(["\'])(.*?)\1', working)
        if quoted and intent in {IntentType.WRITE_FILE, IntentType.APPEND_FILE}:
            entities.append(
                _entity(
                    EntityType.TEXT_CONTENT,
                    "text_content",
                    quoted.group(2),
                    quoted.group(0),
                )
            )

        if intent is IntentType.CREATE_FILE:
            name = re.sub(r"^create\s+", "", working, flags=re.IGNORECASE)
            name = re.sub(
                r"^(?:a )?(?:(?:text|markdown|json|csv|python|html|"
                r"css|javascript|yaml) )?"
                r"file(?: named| called)?\s*",
                "",
                name,
                flags=re.IGNORECASE,
            ).strip()
            if name:
                self._file_name("file_name", name, entities)
            return

        if intent in {IntentType.WRITE_FILE, IntentType.APPEND_FILE}:
            name_match = re.search(r"\b(?:into|to)\s+(.+)$", working, re.IGNORECASE)
            if name_match:
                self._file_name("file_name", name_match.group(1).strip(), entities)
            return

        prefixes = {
            IntentType.READ_FILE: (
                r"^(?:read(?: the file)?|show (?:the )?contents of)\s+"
            ),
            IntentType.OPEN_FILE: r"^open\s+",
            IntentType.DELETE_FILE: r"^delete(?: the)?\s+",
            IntentType.GET_FILE_INFORMATION: (
                r"^(?:show (?:information|info) about|"
                r"get (?:information|info) (?:about|for))\s+"
            ),
        }
        if intent is IntentType.CHECK_FILE_EXISTENCE:
            match = re.match(
                r"^(?:does\s+(.+?)\s+exist|check whether\s+(.+?)\s+exists?)$",
                working,
                re.IGNORECASE,
            )
            if match:
                self._file_name(
                    "file_name", (match.group(1) or match.group(2)).strip(), entities
                )
            return
        if intent is IntentType.SEARCH_FILE:
            query = re.sub(
                r"^(?:find|search for)\s+", "", working, flags=re.IGNORECASE
            ).strip()
            extension_match = re.fullmatch(
                r"(text|markdown|json|csv|python|html|css|javascript|yaml) files?",
                query,
                re.IGNORECASE,
            )
            if extension_match:
                extension = EXTENSIONS[extension_match.group(1).casefold()]
                entities.append(
                    _entity(
                        EntityType.FILE_EXTENSION, "search_extension", extension, query
                    )
                )
            elif query:
                self._file_name("file_name", query, entities)
            return
        prefix = prefixes.get(intent)
        if prefix:
            name, count = re.subn(prefix, "", working, flags=re.IGNORECASE)
            name = name.strip()
            if count and name:
                self._file_name("file_name", name, entities)

    @staticmethod
    def _rename(original: str, entities: list[CommandEntity]) -> None:
        match = re.match(r"^rename\s+(.+?)\s+to\s+(.+)$", original, re.IGNORECASE)
        if not match:
            return
        source = match.group(1).strip()
        location = re.search(
            rf"\s+(?:in|on)\s+({_LOCATION_EXPRESSION})$", source, re.IGNORECASE
        )
        if location:
            entities.append(
                _entity(
                    EntityType.LOCATION,
                    "location",
                    _location_value(location.group(1)),
                    location.group(1),
                )
            )
            source = source[: location.start()].strip()
        RuleBasedEntityExtractor._file_name("source_file", source, entities)
        RuleBasedEntityExtractor._file_name(
            "new_name", match.group(2).strip(), entities
        )

    @staticmethod
    def _transfer(original: str, entities: list[CommandEntity]) -> None:
        match = re.match(
            rf"^(?:copy|move)\s+(.+?)(?:\s+from\s+({_LOCATION_EXPRESSION}))?"
            rf"\s+to\s+({_LOCATION_EXPRESSION})$",
            original,
            re.IGNORECASE,
        )
        if not match:
            return
        RuleBasedEntityExtractor._file_name(
            "source_file", match.group(1).strip(), entities
        )
        if match.group(2):
            entities.append(
                _entity(
                    EntityType.LOCATION,
                    "source_location",
                    _location_value(match.group(2)),
                    match.group(2),
                )
            )
        entities.append(
            _entity(
                EntityType.LOCATION,
                "destination",
                _location_value(match.group(3)),
                match.group(3),
            )
        )

    @staticmethod
    def _folder(original: str, entities: list[CommandEntity]) -> None:
        working = original
        location = re.search(
            rf"\s+(?:in|on)\s+({_LOCATION_EXPRESSION})$", working, re.IGNORECASE
        )
        if location:
            entities.append(
                _entity(
                    EntityType.LOCATION,
                    "location",
                    _location_value(location.group(1)),
                    location.group(1),
                )
            )
            working = working[: location.start()].strip()
        match = re.search(
            r"(?:folder|directory)(?: named| called)?\s+(.+)$",
            working,
            re.IGNORECASE,
        )
        if match:
            entities.append(
                _entity(
                    EntityType.FOLDER_NAME,
                    "folder_name",
                    match.group(1).strip(),
                    match.group(1).strip(),
                )
            )

    @staticmethod
    def _file_name(name: str, value: str, entities: list[CommandEntity]) -> None:
        entities.append(_entity(EntityType.FILE_NAME, name, value, value))
