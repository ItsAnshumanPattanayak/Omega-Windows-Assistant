"""Typed browser records that never retain backend objects or private state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from omega.core.exceptions import ModelValidationError
from omega.models._serialization import (
    JsonValue,
    serialize_value,
    utc_now,
    validate_json_mapping,
    validate_utc_timestamp,
)


class BrowserSessionState(StrEnum):
    """Lifecycle of the one Omega-controlled browser session."""

    STOPPED = "stopped"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    FAILED = "failed"


@dataclass(frozen=True)
class TabSummary:
    """Safe snapshot of an Omega-controlled tab."""

    tab_id: UUID
    title: str
    url: str
    current: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.tab_id, UUID):
            raise ModelValidationError("tab_id must be a UUID.")
        if not isinstance(self.title, str) or not isinstance(self.url, str):
            raise ModelValidationError("Tab title and URL must be strings.")
        if not isinstance(self.current, bool):
            raise ModelValidationError("current must be a boolean.")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "tab_id": str(self.tab_id),
            "title": self.title,
            "url": self.url,
            "current": self.current,
        }


@dataclass(frozen=True)
class PageSummary:
    """Bounded, visible page information with no HTML or browser storage."""

    tab_id: UUID
    title: str
    url: str
    visible_text: str = ""
    load_state: str = "unknown"
    text_match_count: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.tab_id, UUID):
            raise ModelValidationError("tab_id must be a UUID.")
        for name in ("title", "url", "visible_text", "load_state"):
            if not isinstance(getattr(self, name), str):
                raise ModelValidationError(f"{name} must be a string.")
        if self.text_match_count is not None and (
            isinstance(self.text_match_count, bool) or self.text_match_count < 0
        ):
            raise ModelValidationError("text_match_count must be non-negative.")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "tab_id": str(self.tab_id),
            "title": self.title,
            "url": self.url,
            "visible_text": self.visible_text,
            "load_state": self.load_state,
            "text_match_count": self.text_match_count,
        }


@dataclass(frozen=True)
class NavigationRequest:
    """Validated navigation request passed to the browser manager."""

    url: str
    open_new_tab: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url.strip():
            raise ModelValidationError("Navigation URL must not be empty.")
        if not isinstance(self.open_new_tab, bool):
            raise ModelValidationError("open_new_tab must be a boolean.")


@dataclass(frozen=True)
class SearchRequest:
    """Bounded search request using a trusted engine identifier."""

    query: str
    engine: str

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip():
            raise ModelValidationError("Search query must not be empty.")
        if not isinstance(self.engine, str) or not self.engine.strip():
            raise ModelValidationError("Search engine must not be empty.")


@dataclass(frozen=True)
class Bookmark:
    """Omega-managed bookmark; never a browser-native bookmark record."""

    name: str
    url: str
    bookmark_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.bookmark_id, UUID):
            raise ModelValidationError("bookmark_id must be a UUID.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ModelValidationError("Bookmark name must not be empty.")
        if not isinstance(self.url, str) or not self.url.strip():
            raise ModelValidationError("Bookmark URL must not be empty.")
        object.__setattr__(
            self, "created_at", validate_utc_timestamp(self.created_at, "created_at")
        )
        object.__setattr__(
            self, "updated_at", validate_utc_timestamp(self.updated_at, "updated_at")
        )
        if self.updated_at < self.created_at:
            raise ModelValidationError("updated_at must not precede created_at.")
        object.__setattr__(
            self, "metadata", validate_json_mapping(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "bookmark_id": str(self.bookmark_id),
            "name": self.name,
            "url": self.url,
            "created_at": serialize_value(self.created_at),
            "updated_at": serialize_value(self.updated_at),
            "metadata": self.metadata,
        }
