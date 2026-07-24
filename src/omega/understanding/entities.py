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
_NOTE_INTENTS = frozenset(
    {
        IntentType.CREATE_NOTE,
        IntentType.SHOW_NOTE,
        IntentType.UPDATE_NOTE,
        IntentType.APPEND_NOTE,
        IntentType.SEARCH_NOTES,
        IntentType.PIN_NOTE,
        IntentType.UNPIN_NOTE,
        IntentType.ARCHIVE_NOTE,
        IntentType.RESTORE_NOTE,
        IntentType.DELETE_NOTE,
        IntentType.TAG_NOTE,
        IntentType.UNTAG_NOTE,
        IntentType.EXPORT_NOTES,
        IntentType.IMPORT_NOTES,
        IntentType.LIST_NOTES,
    }
)
_TASK_LIST_INTENTS = frozenset(
    {
        IntentType.CREATE_TASK_LIST,
        IntentType.LIST_TASK_LISTS,
        IntentType.SHOW_TASK_LIST,
        IntentType.UPDATE_TASK_LIST,
        IntentType.ARCHIVE_TASK_LIST,
        IntentType.RESTORE_TASK_LIST,
        IntentType.DELETE_TASK_LIST,
    }
)
_TASK_INTENTS = frozenset(
    {
        IntentType.CREATE_TASK,
        IntentType.LIST_TASKS,
        IntentType.SHOW_TASK,
        IntentType.UPDATE_TASK,
        IntentType.COMPLETE_TASK,
        IntentType.REOPEN_TASK,
        IntentType.CANCEL_TASK,
        IntentType.ARCHIVE_TASK,
        IntentType.RESTORE_TASK,
        IntentType.DELETE_TASK,
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
_PRODUCTIVITY_INTENTS = _NOTE_INTENTS | _TASK_LIST_INTENTS | _TASK_INTENTS
_KNOWLEDGE_INTENTS = frozenset(
    {
        IntentType.CREATE_KNOWLEDGE_COLLECTION,
        IntentType.LIST_KNOWLEDGE_COLLECTIONS,
        IntentType.SHOW_KNOWLEDGE_COLLECTION,
        IntentType.UPDATE_KNOWLEDGE_COLLECTION,
        IntentType.ARCHIVE_KNOWLEDGE_COLLECTION,
        IntentType.RESTORE_KNOWLEDGE_COLLECTION,
        IntentType.DELETE_KNOWLEDGE_COLLECTION,
        IntentType.IMPORT_KNOWLEDGE_DOCUMENT,
        IntentType.LIST_KNOWLEDGE_DOCUMENTS,
        IntentType.SHOW_KNOWLEDGE_DOCUMENT,
        IntentType.MOVE_KNOWLEDGE_DOCUMENT,
        IntentType.REINDEX_KNOWLEDGE_DOCUMENT,
        IntentType.REMOVE_KNOWLEDGE_DOCUMENT,
        IntentType.SEARCH_KNOWLEDGE,
        IntentType.ASK_KNOWLEDGE,
        IntentType.SHOW_KNOWLEDGE_SOURCES,
        IntentType.EXPORT_KNOWLEDGE_RESULTS,
    }
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
        if intent in _KNOWLEDGE_INTENTS:
            self._knowledge(original, intent, entities)
        elif intent in _PRODUCTIVITY_INTENTS:
            self._productivity(original, intent, entities)
        elif intent in {
            IntentType.CREATE_REMINDER,
            IntentType.CREATE_RECURRING_REMINDER,
            IntentType.CREATE_ALARM,
            IntentType.CREATE_RECURRING_ALARM,
            IntentType.START_TIMER,
            IntentType.PAUSE_TIMER,
            IntentType.RESUME_TIMER,
            IntentType.CANCEL_TIMER,
            IntentType.SHOW_TIMER,
            IntentType.SNOOZE_REMINDER,
            IntentType.SNOOZE_ALARM,
            IntentType.SHOW_REMINDER,
            IntentType.UPDATE_REMINDER,
            IntentType.CANCEL_REMINDER,
            IntentType.COMPLETE_REMINDER,
            IntentType.SHOW_ALARM,
            IntentType.UPDATE_ALARM,
            IntentType.CANCEL_ALARM,
            IntentType.DISMISS_ALARM,
        }:
            self._scheduling(original, intent, entities)
        elif intent in {
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
    def _knowledge(
        original: str, intent: IntentType, entities: list[CommandEntity]
    ) -> None:
        text = original.strip()
        quoted = re.findall(r'["\']([^"\']+)["\']', text)
        if intent is IntentType.CREATE_KNOWLEDGE_COLLECTION:
            match = re.search(
                r"knowledge collection(?: called| named)?\s+(.+)$",
                text,
                re.IGNORECASE,
            )
            if match:
                value = quoted[-1] if quoted else match.group(1).strip()
                entities.append(
                    _entity(
                        EntityType.KNOWLEDGE_COLLECTION,
                        "collection_name",
                        value,
                        value,
                    )
                )
            return
        if intent is IntentType.IMPORT_KNOWLEDGE_DOCUMENT:
            path = re.search(
                r'([A-Za-z]:[\\/][^"\r\n]+?\.(?:pdf|docx|txt|md|markdown)'
                r'|[^"\s]+\.(?:pdf|docx|txt|md|markdown))',
                text,
                re.IGNORECASE,
            )
            if path:
                value = path.group(1).strip()
                entities.append(_entity(EntityType.PATH, "document_path", value, value))
            collection = re.search(
                r"\b(?:into|to)\s+(.+?)(?:\s+collection)?$",
                text,
                re.IGNORECASE,
            )
            if collection:
                value = collection.group(1).strip()
                if not re.fullmatch(r"(?:my )?knowledge base", value, re.IGNORECASE):
                    entities.append(
                        _entity(
                            EntityType.KNOWLEDGE_COLLECTION,
                            "collection_name",
                            value,
                            value,
                        )
                    )
            return
        if intent in {IntentType.SEARCH_KNOWLEDGE, IntentType.ASK_KNOWLEDGE}:
            if intent is IntentType.SEARCH_KNOWLEDGE:
                match = re.search(r"\bfor\s+(.+)$", text, re.IGNORECASE)
                prefix = re.match(r"^search\s+(.+?)\s+for\s+", text, re.IGNORECASE)
                if prefix:
                    value = prefix.group(1).strip()
                    if value.casefold() not in {
                        "my documents",
                        "my knowledge base",
                    }:
                        entities.append(
                            _entity(
                                EntityType.KNOWLEDGE_COLLECTION,
                                "collection_name",
                                value,
                                value,
                            )
                        )
            else:
                match = re.match(
                    r"^ask (?:my documents|my knowledge base)\s+(.+)$",
                    text,
                    re.IGNORECASE,
                )
                if match is None:
                    match = re.match(r"^(what does .+)$", text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                entities.append(
                    _entity(EntityType.SEARCH_QUERY, "knowledge_query", value, value)
                )
            return
        collection_intents = {
            IntentType.SHOW_KNOWLEDGE_COLLECTION,
            IntentType.UPDATE_KNOWLEDGE_COLLECTION,
            IntentType.ARCHIVE_KNOWLEDGE_COLLECTION,
            IntentType.RESTORE_KNOWLEDGE_COLLECTION,
            IntentType.DELETE_KNOWLEDGE_COLLECTION,
            IntentType.LIST_KNOWLEDGE_DOCUMENTS,
        }
        if intent in collection_intents:
            match = re.search(
                r"(?:show|rename|update|archive|restore|delete)\s+(?:the )?(.+?)\s+"
                r"knowledge collection",
                text,
                re.IGNORECASE,
            )
            if intent is IntentType.LIST_KNOWLEDGE_DOCUMENTS:
                match = re.search(r"\bin\s+(.+)$", text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                entities.append(
                    _entity(
                        EntityType.KNOWLEDGE_COLLECTION,
                        "collection_reference",
                        value,
                        value,
                    )
                )
            return
        document_intents = {
            IntentType.SHOW_KNOWLEDGE_DOCUMENT,
            IntentType.MOVE_KNOWLEDGE_DOCUMENT,
            IntentType.REINDEX_KNOWLEDGE_DOCUMENT,
            IntentType.REMOVE_KNOWLEDGE_DOCUMENT,
        }
        if intent in document_intents:
            reference = re.sub(
                r"^(?:show|move|re-?index|remove|delete)\s+(?:the )?",
                "",
                text,
                flags=re.IGNORECASE,
            )
            reference = re.sub(
                r"\s+(?:knowledge )?document(?:\s+.*)?$",
                "",
                reference,
                flags=re.IGNORECASE,
            )
            entities.append(
                _entity(
                    EntityType.KNOWLEDGE_DOCUMENT,
                    "document_reference",
                    quoted[0] if quoted else reference.strip(),
                    reference.strip(),
                )
            )
            if intent is IntentType.MOVE_KNOWLEDGE_DOCUMENT:
                destination = re.search(
                    r"\bto\s+(.+?)(?:\s+collection)?$", text, re.IGNORECASE
                )
                if destination:
                    value = destination.group(1).strip()
                    entities.append(
                        _entity(
                            EntityType.KNOWLEDGE_COLLECTION,
                            "collection_name",
                            value,
                            value,
                        )
                    )

    @staticmethod
    def _productivity(
        original: str, intent: IntentType, entities: list[CommandEntity]
    ) -> None:
        text = original.strip().rstrip("?!")
        quoted = re.findall(r'["“](.+?)["”]', text)
        if intent is IntentType.CREATE_NOTE:
            value = re.sub(
                r"^create (?:a )?note(?: called| titled| named)?\s+",
                "",
                text,
                flags=re.IGNORECASE,
            )
            title, body = value, ""
            match = re.match(r"(.+?)\s+with\s+(.+)$", value, re.IGNORECASE)
            if match:
                title, body = match.group(1), match.group(2)
            entities.append(_entity(EntityType.NOTE, "note_title", title, title))
            if body:
                entities.append(
                    _entity(EntityType.TEXT_CONTENT, "note_body", body, body)
                )
        elif intent is IntentType.CREATE_TASK:
            selected_list = re.search(
                r"\btask\s+to\s+(?:my\s+)?(.+?)\s+list\b",
                text,
                re.IGNORECASE,
            )
            if selected_list:
                entities.append(
                    _entity(
                        EntityType.TASK_LIST,
                        "task_list_name",
                        selected_list.group(1),
                        selected_list.group(1),
                    )
                )
            value = re.sub(
                r"^(?:create|add) (?:a )?task(?: to .+? list)?(?: to)?\s+",
                "",
                text,
                flags=re.IGNORECASE,
            )
            if re.fullmatch(
                r"(?:create|add) (?:a )?task(?: to .+ list)?",
                text,
                re.IGNORECASE,
            ):
                value = ""
            entities.append(_entity(EntityType.TASK, "task_title", value, value))
        elif intent is IntentType.CREATE_TASK_LIST:
            value = re.sub(
                r"^create (?:a )?task list(?: called| named)?\s+",
                "",
                text,
                flags=re.IGNORECASE,
            )
            entities.append(
                _entity(EntityType.TASK_LIST, "task_list_name", value, value)
            )
        else:
            transfer_file = re.search(
                r"\b(?:to|from)\s+([^\s]+\.(?:json|md))$",
                text,
                re.IGNORECASE,
            )
            if intent in {IntentType.EXPORT_NOTES, IntentType.IMPORT_NOTES}:
                if transfer_file:
                    entities.append(
                        _entity(
                            EntityType.FILE_NAME,
                            "file_name",
                            transfer_file.group(1),
                            transfer_file.group(1),
                        )
                    )
                return
            reminder_link = re.match(
                r"^(?:link|unlink) reminder\s+"
                r"([0-9a-f]{8}-[0-9a-f-]{27,})\s+(?:to|from)\s+"
                r"(?:the\s+)?(.+?)\s+task$",
                text,
                re.IGNORECASE,
            )
            if (
                intent
                in {IntentType.LINK_TASK_REMINDER, IntentType.UNLINK_TASK_REMINDER}
                and reminder_link
            ):
                entities.extend(
                    (
                        _entity(
                            EntityType.SCHEDULE,
                            "schedule_id",
                            reminder_link.group(1),
                            reminder_link.group(1),
                        ),
                        _entity(
                            EntityType.TASK,
                            "reference",
                            reminder_link.group(2),
                            reminder_link.group(2),
                        ),
                    )
                )
                return
            deadline_link = re.match(
                r"^remind me about (?:the )?(.+?) task at .+$",
                text,
                re.IGNORECASE,
            )
            if intent is IntentType.LINK_TASK_REMINDER and deadline_link:
                reference = deadline_link.group(1)
                entities.append(
                    _entity(EntityType.TASK, "reference", reference, reference)
                )
                return
            append = re.match(
                r"^(?:add|append)\s+(.+?)\s+to\s+(?:the\s+)?(.+?)\s+note$",
                text,
                re.IGNORECASE,
            )
            if intent is IntentType.APPEND_NOTE and append:
                content = append.group(1).strip(' "“”')
                reference = append.group(2).strip(' "“”')
                entities.extend(
                    (
                        _entity(
                            EntityType.TEXT_CONTENT,
                            "note_body",
                            content,
                            append.group(1),
                        ),
                        _entity(EntityType.NOTE, "reference", reference, reference),
                    )
                )
                return
            query = re.search(r"\b(?:for|with)\s+(.+)$", text, re.IGNORECASE)
            if intent in {IntentType.SEARCH_NOTES, IntentType.SEARCH_TASKS} and query:
                entities.append(
                    _entity(
                        EntityType.SEARCH_QUERY,
                        "search_query",
                        query.group(1),
                        query.group(1),
                    )
                )
            priority = re.search(
                r"\b(none|low|medium|high|urgent)\b$", text, re.IGNORECASE
            )
            if priority:
                entities.append(
                    _entity(
                        EntityType.PRIORITY,
                        "priority",
                        priority.group(1).casefold(),
                        priority.group(1),
                    )
                )
            tag = re.search(
                r"\b(?:with|tag)\s+(.+?)(?:\s+(?:note|task))?$", text, re.IGNORECASE
            )
            if intent in {IntentType.TAG_NOTE, IntentType.TAG_TASK} and tag:
                entities.append(
                    _entity(EntityType.TAG, "tag", tag.group(1), tag.group(1))
                )
            removed_tag = re.match(
                r"^remove tag\s+(.+?)\s+from\s+",
                text,
                re.IGNORECASE,
            )
            if intent in {IntentType.UNTAG_NOTE, IntentType.UNTAG_TASK} and removed_tag:
                entities.append(
                    _entity(
                        EntityType.TAG,
                        "tag",
                        removed_tag.group(1),
                        removed_tag.group(1),
                    )
                )
            reference = re.sub(
                r"^(?:show|open|view|pin|unpin|archive|restore|delete|mark|"
                r"complete|reopen|cancel|set|remove|move|tag)\s+(?:the )?",
                "",
                text,
                flags=re.IGNORECASE,
            )
            reference = re.sub(
                r"\s+(?:note|task|task list)(?:\s+.*)?$",
                "",
                reference,
                flags=re.IGNORECASE,
            )
            if quoted:
                reference = quoted[-1]
            entity_type = (
                EntityType.NOTE
                if intent in _NOTE_INTENTS
                else (
                    EntityType.TASK_LIST
                    if intent in _TASK_LIST_INTENTS
                    else EntityType.TASK
                )
            )
            entities.append(_entity(entity_type, "reference", reference, reference))

    @staticmethod
    def _scheduling(
        original: str, intent: IntentType, entities: list[CommandEntity]
    ) -> None:
        text = original.strip().rstrip("?!")
        duration = re.search(
            r"\b(\d+)\s*(seconds?|minutes?|hours?|days?)\b", text, re.IGNORECASE
        )
        if duration:
            amount = int(duration.group(1))
            unit = duration.group(2).casefold()
            multiplier = (
                1
                if unit.startswith("second")
                else (
                    60
                    if unit.startswith("minute")
                    else 3600 if unit.startswith("hour") else 86400
                )
            )
            entities.append(
                CommandEntity(
                    EntityType.DURATION,
                    amount * multiplier,
                    raw_value=duration.group(0),
                    name="duration_seconds",
                    confidence=1.0,
                )
            )
        clock = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text, re.IGNORECASE)
        if clock:
            entities.append(
                _entity(
                    EntityType.DATE_TIME,
                    "clock_time",
                    clock.group(0).casefold(),
                    clock.group(0),
                )
            )
        if intent in {IntentType.CREATE_REMINDER, IntentType.CREATE_RECURRING_REMINDER}:
            message = re.sub(r"^remind me\s+", "", text, flags=re.IGNORECASE)
            entities.append(
                _entity(EntityType.TEXT_CONTENT, "message", message, message)
            )
        label = re.search(
            r"^(?:pause|resume|cancel|show)\s+(?:the\s+)?(.+?)\s+timer$",
            text,
            re.IGNORECASE,
        )
        if label:
            entities.append(
                _entity(EntityType.SCHEDULE, "title", label.group(1), label.group(1))
            )
        schedule_reference = re.search(
            r"^(?:show|view|cancel|complete|mark|dismiss|snooze|update|reschedule)"
            r"\s+(?:the\s+)?(.+?)\s+(?:reminder|alarm)\b",
            text,
            re.IGNORECASE,
        )
        if schedule_reference:
            raw = schedule_reference.group(1).strip()
            if raw.casefold() not in {"this", "the"}:
                entities.append(_entity(EntityType.SCHEDULE, "title", raw, raw))
        trailing_reference = re.search(
            r"^(?:show|view|cancel|complete|mark|dismiss|snooze|update|reschedule)"
            r"\s+(?:the\s+)?(?:reminder|alarm)\s+"
            r"(?!for\b|at\b|to\b|complete\b)(.+?)"
            r"(?:\s+(?:for|at|to)\s+.+)?$",
            text,
            re.IGNORECASE,
        )
        if trailing_reference and not any(item.name == "title" for item in entities):
            raw = re.sub(
                r"^(?:called|named)\s+",
                "",
                trailing_reference.group(1).strip(),
                flags=re.IGNORECASE,
            )
            entities.append(_entity(EntityType.SCHEDULE, "title", raw, raw))

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
            destination = re.search(
                r"\btask\s+to\s+(.+?)(?:\s+list)?$",
                text,
                re.IGNORECASE,
            )
            if intent is IntentType.MOVE_TASK and destination:
                raw_destination = destination.group(1)
                entities.append(
                    _entity(
                        EntityType.TASK_LIST,
                        "task_list_name",
                        raw_destination,
                        raw_destination,
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
