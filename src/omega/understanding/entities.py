"""Deterministic extraction of canonical Phase 1 command entities."""

from __future__ import annotations

import re
from pathlib import PureWindowsPath

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
    """Extract known applications and tightly scoped file/folder values."""

    def __init__(self, aliases: ApplicationAliasRegistry) -> None:
        self.aliases = aliases

    def extract(self, original: str, intent: IntentType) -> list[CommandEntity]:
        entities: list[CommandEntity] = []
        if intent in {
            IntentType.SET_VOLUME,
            IntentType.INCREASE_VOLUME,
            IntentType.DECREASE_VOLUME,
            IntentType.SET_BRIGHTNESS,
            IntentType.INCREASE_BRIGHTNESS,
            IntentType.DECREASE_BRIGHTNESS,
            IntentType.OPEN_WINDOWS_SETTINGS,
            IntentType.SEARCH_PROCESS,
            IntentType.GET_PROCESS_INFORMATION,
        }:
            self._system(original, intent, entities)
        elif intent in {
            IntentType.OPEN_WEBSITE,
            IntentType.SEARCH_WEB,
            IntentType.CLOSE_TAB,
            IntentType.SWITCH_TAB,
            IntentType.FIND_TEXT_ON_PAGE,
            IntentType.OPEN_BOOKMARK,
            IntentType.SAVE_BOOKMARK,
        }:
            self._browser(original, intent, entities)
        else:
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
        elif intent in {
            IntentType.CREATE_FOLDER,
            IntentType.OPEN_FOLDER,
            IntentType.LIST_FOLDER,
            IntentType.RENAME_FOLDER,
            IntentType.COPY_FOLDER,
            IntentType.MOVE_FOLDER,
            IntentType.DELETE_FOLDER,
            IntentType.CHECK_FOLDER_EXISTENCE,
            IntentType.GET_FOLDER_INFORMATION,
            IntentType.SEARCH_FOLDER,
        }:
            self._folder_command(original, intent, entities)
        return entities

    @staticmethod
    def _system(
        original: str,
        intent: IntentType,
        entities: list[CommandEntity],
    ) -> None:
        text = original.strip().rstrip("?!")
        if intent in {
            IntentType.SET_VOLUME,
            IntentType.INCREASE_VOLUME,
            IntentType.DECREASE_VOLUME,
            IntentType.SET_BRIGHTNESS,
            IntentType.INCREASE_BRIGHTNESS,
            IntentType.DECREASE_BRIGHTNESS,
        }:
            values = re.findall(r"(?<![-\d])(\d{1,3})(?:\s*percent|\s*%)?", text)
            if len(values) == 1:
                value = int(values[0])
                entities.append(
                    CommandEntity(
                        EntityType.PERCENTAGE,
                        value,
                        raw_value=values[0],
                        name="percentage",
                        confidence=1.0,
                    )
                )
            return
        if intent is IntentType.OPEN_WINDOWS_SETTINGS:
            match = re.match(r"^open\s+(.+?)\s+settings$", text, re.IGNORECASE)
            aliases = {
                "power and battery": "power",
                "bluetooth and devices": "bluetooth",
                "network and internet": "network",
                "windows update": "windows_update",
            }
            if match:
                raw = " ".join(match.group(1).casefold().split())
                page = aliases.get(raw, raw)
                entities.append(
                    _entity(EntityType.SETTINGS_PAGE, "settings_page", page, raw)
                )
            return
        process = re.sub(
            r"^(?:find|search for)\s+(?:a\s+)?process(?:\s+named)?\s+|"
            r"^show\s+process\s+information\s+for\s+|^is\s+|\s+running$",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        if process:
            entities.append(
                _entity(EntityType.PROCESS, "process_name", process, process)
            )

    @staticmethod
    def _browser(
        original: str,
        intent: IntentType,
        entities: list[CommandEntity],
    ) -> None:
        text = original.strip().rstrip("?!")
        if intent is IntentType.OPEN_WEBSITE:
            value = re.sub(
                r"^(?:open|visit|go to)\s+(?:the\s+)?(?:website\s+)?",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()
            if re.fullmatch(
                r"(?:[a-z0-9-]+\s+dot\s+)+[a-z]{2,}",
                value,
                flags=re.IGNORECASE,
            ):
                value = re.sub(r"\s+dot\s+", ".", value, flags=re.IGNORECASE)
            if "://" not in value:
                value = f"https://{value}"
            entities.append(_entity(EntityType.URL, "url", value, value))
            return
        if intent is IntentType.SEARCH_WEB:
            query = re.sub(
                r"^(?:search\s+(?:the\s+)?web\s+for|web\s+search\s+for)\s+",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()
            if query:
                entities.append(
                    _entity(EntityType.WEB_QUERY, "search_query", query, query)
                )
            return
        if intent in {IntentType.CLOSE_TAB, IntentType.SWITCH_TAB}:
            reference = re.sub(
                r"^(?:close|switch(?:\s+to)?)\s+tab\s*",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()
            word_numbers = {
                "one": "1",
                "two": "2",
                "three": "3",
                "four": "4",
                "five": "5",
                "six": "6",
                "seven": "7",
                "eight": "8",
                "nine": "9",
                "ten": "10",
            }
            reference = word_numbers.get(reference.casefold(), reference)
            if reference:
                entities.append(_entity(EntityType.TAB, "tab", reference, reference))
            return
        if intent is IntentType.FIND_TEXT_ON_PAGE:
            match = re.match(
                r"^find\s+(?:the\s+)?(?:word|text)\s+(.+?)\s+on\s+(?:this|the)\s+page$",
                text,
                flags=re.IGNORECASE,
            )
            if match:
                value = match.group(1).strip(" \"'")
                entities.append(
                    _entity(EntityType.TEXT_CONTENT, "text_content", value, value)
                )
            return
        if intent in {IntentType.OPEN_BOOKMARK, IntentType.SAVE_BOOKMARK}:
            if intent is IntentType.OPEN_BOOKMARK:
                name = re.sub(
                    r"^open\s+bookmark\s+",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )
            else:
                name = re.sub(
                    r"^save\s+(?:this\s+page\s+as\s+|bookmark\s+)" r"(?:bookmark\s+)?",
                    "",
                    text,
                    flags=re.IGNORECASE,
                )
            name = name.strip(" \"'")
            if name:
                entities.append(
                    _entity(EntityType.BOOKMARK, "bookmark_name", name, name)
                )

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

    def _folder_command(
        self,
        original: str,
        intent: IntentType,
        entities: list[CommandEntity],
    ) -> None:
        if intent is IntentType.CREATE_FOLDER:
            self._create_folder(original, entities)
        elif intent in {
            IntentType.OPEN_FOLDER,
            IntentType.LIST_FOLDER,
            IntentType.CHECK_FOLDER_EXISTENCE,
            IntentType.GET_FOLDER_INFORMATION,
            IntentType.DELETE_FOLDER,
        }:
            self._folder_target(original, intent, entities)
        elif intent is IntentType.RENAME_FOLDER:
            self._rename_folder(original, entities)
        elif intent in {IntentType.COPY_FOLDER, IntentType.MOVE_FOLDER}:
            self._transfer_folder(original, entities)
        elif intent is IntentType.SEARCH_FOLDER:
            self._search_folder(original, entities)

    def _create_folder(self, original: str, entities: list[CommandEntity]) -> None:
        working, location, nested = self._split_location(original)
        if location:
            self._append_location("location", location, entities)
        if nested:
            entities.append(_entity(EntityType.PATH, "parent_path", nested, nested))
        match = re.search(
            r"(?:folder|directory)(?: named| called)?\s+(.+)$",
            working,
            re.IGNORECASE,
        )
        if match:
            name = self._strip_folder_words(match.group(1))
            if name:
                entities.append(
                    _entity(EntityType.FOLDER_NAME, "folder_name", name, name)
                )

    def _folder_target(
        self,
        original: str,
        intent: IntentType,
        entities: list[CommandEntity],
    ) -> None:
        prefixes = {
            IntentType.OPEN_FOLDER: r"^open\s+",
            IntentType.LIST_FOLDER: (
                r"^(?:show (?:files|the contents) inside|show (?:the )?contents of|"
                r"list (?:files inside|(?:the )?contents of)|what is inside)\s+"
            ),
            IntentType.DELETE_FOLDER: r"^delete(?: the)?\s+",
            IntentType.GET_FOLDER_INFORMATION: (
                r"^(?:show (?:information|info) about|get (?:information|info) "
                r"(?:about|for)|how large is|count (?:the )?items inside)\s+"
            ),
        }
        working = original.strip()
        if intent is IntentType.CHECK_FOLDER_EXISTENCE:
            match = re.match(r"^does\s+(.+?)\s+exist(.*)$", working, re.IGNORECASE)
            if match:
                working = f"{match.group(1)}{match.group(2)}"
            else:
                match = re.match(
                    r"^check whether\s+(.+?)\s+exists?(.*)$",
                    working,
                    re.IGNORECASE,
                )
                if match:
                    working = f"{match.group(1)}{match.group(2)}"
                else:
                    working = re.sub(
                        r"^is there (?:a )?(?:folder|directory) named\s+",
                        "",
                        working,
                        flags=re.IGNORECASE,
                    ).strip()
        else:
            working = re.sub(prefixes[intent], "", working, flags=re.IGNORECASE).strip()
        working, location, nested = self._split_location(working)
        direct_location = self._logical_path(working)
        if direct_location is not None:
            location, nested = direct_location
            working = ""
        if location:
            self._append_location("location", location, entities)
        target = self._strip_folder_words(working)
        if nested:
            target = PureWindowsPath(nested, target).as_posix() if target else nested
        if target:
            entities.append(
                _entity(EntityType.FOLDER_NAME, "folder_name", target, target)
            )
        if intent is IntentType.GET_FOLDER_INFORMATION and re.match(
            r"^how large is", original, re.IGNORECASE
        ):
            entities.append(
                CommandEntity(
                    EntityType.BOOLEAN,
                    True,
                    raw_value="recursive",
                    name="recursive",
                    confidence=1.0,
                )
            )

    def _rename_folder(self, original: str, entities: list[CommandEntity]) -> None:
        working, location, nested = self._split_location(original)
        match = re.match(r"^rename\s+(.+?)\s+to\s+(.+)$", working, re.IGNORECASE)
        if not match:
            return
        source = self._strip_folder_words(match.group(1))
        new_name = self._strip_folder_words(match.group(2))
        direct_location = self._logical_path(source)
        if direct_location is not None:
            location, direct_path = direct_location
            source = direct_path or ""
        if nested:
            source = nested
        if location:
            self._append_location("location", location, entities)
        if source:
            entities.append(
                _entity(EntityType.FOLDER_NAME, "source_folder", source, source)
            )
        if new_name:
            entities.append(
                _entity(EntityType.FOLDER_NAME, "new_name", new_name, new_name)
            )

    def _transfer_folder(self, original: str, entities: list[CommandEntity]) -> None:
        match = re.match(
            rf"^(?:copy|move)\s+(.+?)(?:\s+from\s+({_LOCATION_EXPRESSION})(?:[\\/](.+?))?)?"
            rf"\s+to\s+({_LOCATION_EXPRESSION})$",
            original,
            re.IGNORECASE,
        )
        if not match:
            return
        source = self._strip_folder_words(match.group(1))
        source_location = match.group(2)
        nested = match.group(3)
        direct_location = self._logical_path(source)
        if direct_location is not None:
            source_location, direct_path = direct_location
            source = direct_path or ""
        if nested:
            source = PureWindowsPath(nested, source).as_posix() if source else nested
        if source:
            entities.append(
                _entity(EntityType.FOLDER_NAME, "source_folder", source, source)
            )
        if source_location:
            self._append_location("source_location", source_location, entities)
        self._append_location("destination", match.group(4), entities)

    def _search_folder(self, original: str, entities: list[CommandEntity]) -> None:
        working = re.sub(
            r"^(?:find|search for)\s+",
            "",
            original,
            flags=re.IGNORECASE,
        ).strip()
        working = re.sub(
            r"^(?:a )?folders?(?: named)?\s+",
            "",
            working,
            flags=re.IGNORECASE,
        ).strip()
        working, location, nested = self._split_location(working)
        if location:
            self._append_location("location", location, entities)
        name = self._strip_folder_words(working)
        if nested:
            name = nested
        if name:
            entities.append(_entity(EntityType.FOLDER_NAME, "folder_name", name, name))

    @staticmethod
    def _split_location(text: str) -> tuple[str, str | None, str | None]:
        match = re.search(
            rf"\s+(?:on|in|inside|from)\s+({_LOCATION_EXPRESSION})(?:[\\/](.+))?$",
            text,
            re.IGNORECASE,
        )
        if match is None:
            return text.strip(), None, None
        return (
            text[: match.start()].strip(),
            match.group(1),
            match.group(2).strip() if match.group(2) else None,
        )

    @staticmethod
    def _logical_path(text: str) -> tuple[str, str | None] | None:
        match = re.fullmatch(
            rf"({_LOCATION_EXPRESSION})(?:[\\/](.+))?",
            text.strip(),
            re.IGNORECASE,
        )
        if match is None:
            return None
        return match.group(1), match.group(2).strip() if match.group(2) else None

    @staticmethod
    def _strip_folder_words(value: str) -> str:
        result = value.strip()
        result = re.sub(r"^(?:the |a )", "", result, flags=re.IGNORECASE)
        result = re.sub(
            r"^(?:folder|directory)(?: named| called)?\s+",
            "",
            result,
            flags=re.IGNORECASE,
        )
        result = re.sub(r"\s+(?:folder|directory)$", "", result, flags=re.IGNORECASE)
        return result.strip()

    @staticmethod
    def _append_location(name: str, raw: str, entities: list[CommandEntity]) -> None:
        entities.append(_entity(EntityType.LOCATION, name, _location_value(raw), raw))

    @staticmethod
    def _file_name(name: str, value: str, entities: list[CommandEntity]) -> None:
        entities.append(_entity(EntityType.FILE_NAME, name, value, value))
