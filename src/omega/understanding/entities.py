"""Deterministic extraction of Phase 1 command entities."""

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
}
LOCATIONS = {
    "desktop": "desktop",
    "documents": "documents",
    "downloads": "downloads",
    "pictures": "pictures",
    "music": "music",
    "videos": "videos",
    "home": "home",
    "current directory": "current_directory",
}


def _entity(entity_type: EntityType, name: str, value: str, raw: str) -> CommandEntity:
    return CommandEntity(entity_type, value, raw_value=raw, name=name, confidence=1.0)


class RuleBasedEntityExtractor:
    """Extract known applications, names, content, and logical locations."""

    def __init__(self, aliases: ApplicationAliasRegistry) -> None:
        self.aliases = aliases

    def extract(self, original: str, intent: IntentType) -> list[CommandEntity]:
        entities: list[CommandEntity] = []
        alias = self.aliases.resolve(original)
        if alias and intent in {
            IntentType.OPEN_APPLICATION,
            IntentType.CLOSE_APPLICATION,
            IntentType.CHECK_APPLICATION_STATUS,
        }:
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

        type_match = re.search(
            r"\b(text|markdown|json|csv|python|html) file\b", original, re.IGNORECASE
        )
        if type_match:
            entities.append(
                _entity(
                    EntityType.FILE_EXTENSION,
                    "file_extension",
                    EXTENSIONS[type_match.group(1).casefold()],
                    type_match.group(0),
                )
            )

        location_match = re.search(
            r"\b(Desktop|Documents|Downloads|Pictures|Music|Videos|Home|"
            r"Current directory)\b",
            original,
            re.IGNORECASE,
        )
        if location_match:
            entities.append(
                _entity(
                    EntityType.LOCATION,
                    (
                        "destination"
                        if intent
                        in {
                            IntentType.MOVE_FILE,
                            IntentType.MOVE_FOLDER,
                            IntentType.COPY_FILE,
                            IntentType.COPY_FOLDER,
                        }
                        else "location"
                    ),
                    LOCATIONS[location_match.group(1).casefold()],
                    location_match.group(0),
                )
            )

        quoted = re.search(r'(["\'])(.*?)\1', original)
        if quoted and intent is IntentType.WRITE_FILE:
            entities.append(
                _entity(
                    EntityType.TEXT_CONTENT,
                    "text_content",
                    quoted.group(2),
                    quoted.group(0),
                )
            )

        self._extract_names(original, intent, entities)
        return entities

    def _extract_names(
        self, original: str, intent: IntentType, entities: list[CommandEntity]
    ) -> None:
        if intent is IntentType.CREATE_FOLDER:
            match = re.search(
                r"(?:folder|directory)(?: named| called)?\s+(.+?)"
                r"(?:\s+on\s+(?:Desktop|Documents|Downloads|Pictures|Music|"
                r"Videos|Home))?$",
                original,
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
            return
        if intent is IntentType.CREATE_FILE:
            match = re.search(
                r"(?:file(?: named| called)?|^create)\s+(.+?)"
                r"(?:\s+on\s+(?:Desktop|Documents|Downloads|Pictures|Music|"
                r"Videos|Home))?$",
                original,
                re.IGNORECASE,
            )
            if match:
                value = re.sub(
                    r"^(?:a )?(?:text|markdown|json|csv|python|html) file"
                    r"(?: named| called)?\s+",
                    "",
                    match.group(1),
                    flags=re.IGNORECASE,
                )
                value = value.strip()
                unnamed_file = re.fullmatch(
                    r"(?:a )?(?:(?:text|markdown|json|csv|python|html) )?file",
                    value,
                    re.IGNORECASE,
                )
                if not unnamed_file:
                    entities.append(
                        _entity(EntityType.FILE_NAME, "file_name", value, value)
                    )
            return
        pair = re.search(
            r"^(?:rename|copy|move)\s+(.+?)(?:\s+to\s+(.+))?$", original, re.IGNORECASE
        )
        if pair and intent in {
            IntentType.RENAME_FILE,
            IntentType.RENAME_FOLDER,
            IntentType.COPY_FILE,
            IntentType.COPY_FOLDER,
            IntentType.MOVE_FILE,
            IntentType.MOVE_FOLDER,
        }:
            is_file = intent in {
                IntentType.RENAME_FILE,
                IntentType.COPY_FILE,
                IntentType.MOVE_FILE,
            }
            entities.append(
                _entity(
                    EntityType.FILE_NAME if is_file else EntityType.FOLDER_NAME,
                    "source_file" if is_file else "source_folder",
                    pair.group(1).strip(),
                    pair.group(1).strip(),
                )
            )
            if pair.group(2) and not any(
                item.name == "destination" for item in entities
            ):
                name = (
                    "new_name"
                    if intent in {IntentType.RENAME_FILE, IntentType.RENAME_FOLDER}
                    else "destination"
                )
                entities.append(
                    _entity(
                        EntityType.FILE_NAME if is_file else EntityType.FOLDER_NAME,
                        name,
                        pair.group(2).strip(),
                        pair.group(2).strip(),
                    )
                )
            return
        if intent in {
            IntentType.OPEN_FILE,
            IntentType.READ_FILE,
            IntentType.DELETE_FILE,
            IntentType.SEARCH_FILE,
            IntentType.WRITE_FILE,
        }:
            cleaned = re.sub(r'(["\']).*?\1', "", original)
            match = re.search(r"([\w .-]+\.[A-Za-z0-9]{1,10})", cleaned)
            if match:
                entities.append(
                    _entity(
                        EntityType.FILE_NAME,
                        "file_name",
                        match.group(1).strip(),
                        match.group(1).strip(),
                    )
                )
        elif intent in {
            IntentType.OPEN_FOLDER,
            IntentType.LIST_FOLDER,
            IntentType.DELETE_FOLDER,
        }:
            match = re.search(
                r"(?:open (?:the )?|inside |contents of |delete (?:the )?)"
                r"(.+?)(?: folder)?$",
                original,
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
