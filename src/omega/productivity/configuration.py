"""Strict configuration for local notes and tasks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from omega.productivity.exceptions import ProductivityConfigurationError


@dataclass(frozen=True)
class ProductivityConfiguration:
    """Validated productivity limits; safety switches cannot be widened at runtime."""

    enabled: bool = True
    maximum_notes: int = 5_000
    maximum_task_lists: int = 200
    maximum_tasks: int = 10_000
    maximum_note_title_characters: int = 200
    maximum_note_body_characters: int = 50_000
    maximum_task_title_characters: int = 300
    maximum_task_description_characters: int = 5_000
    maximum_tags_per_item: int = 20
    maximum_tag_characters: int = 50
    maximum_search_query_characters: int = 500
    maximum_search_results: int = 200
    maximum_export_bytes: int = 10_485_760
    allow_markdown_export: bool = True
    allow_json_export: bool = True
    allow_json_import: bool = True
    allow_markdown_import: bool = False
    preserve_archived_items: bool = True
    reminder_linking_enabled: bool = True
    automatically_create_deadline_reminders: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> ProductivityConfiguration:
        """Reject unknown keys, coercion, unsafe switches, and excessive limits."""

        allowed = set(cls.__dataclass_fields__)
        unknown = set(values).difference(allowed)
        if unknown:
            raise ProductivityConfigurationError(
                "Unknown productivity setting(s): " + ", ".join(sorted(unknown))
            )
        defaults = cls()
        merged = {name: values.get(name, getattr(defaults, name)) for name in allowed}
        booleans = {
            "enabled",
            "allow_markdown_export",
            "allow_json_export",
            "allow_json_import",
            "allow_markdown_import",
            "preserve_archived_items",
            "reminder_linking_enabled",
            "automatically_create_deadline_reminders",
        }
        for name in booleans:
            if not isinstance(merged[name], bool):
                raise ProductivityConfigurationError(
                    f"productivity.{name} must be a boolean."
                )
        limits = {
            "maximum_notes": 100_000,
            "maximum_task_lists": 10_000,
            "maximum_tasks": 200_000,
            "maximum_note_title_characters": 1_000,
            "maximum_note_body_characters": 1_000_000,
            "maximum_task_title_characters": 2_000,
            "maximum_task_description_characters": 100_000,
            "maximum_tags_per_item": 100,
            "maximum_tag_characters": 100,
            "maximum_search_query_characters": 5_000,
            "maximum_search_results": 1_000,
            "maximum_export_bytes": 50_000_000,
        }
        for name, maximum in limits.items():
            value = merged[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ProductivityConfigurationError(
                    f"productivity.{name} must be an integer."
                )
            if not 1 <= value <= maximum:
                raise ProductivityConfigurationError(
                    f"productivity.{name} is outside its safe range."
                )
        if merged["allow_markdown_import"]:
            raise ProductivityConfigurationError(
                "Markdown import is not supported because import is JSON-only."
            )
        if merged["automatically_create_deadline_reminders"]:
            raise ProductivityConfigurationError(
                "Automatic deadline reminders must remain disabled."
            )
        return cls(**merged)
