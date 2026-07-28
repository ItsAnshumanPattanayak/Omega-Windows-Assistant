"""Static serializable plugin metadata and lifecycle records."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

from omega.plugins.exceptions import PluginValidationError

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_ENTRY_POINT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:[A-Za-z_][A-Za-z0-9_]*$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class PluginCategory(StrEnum):
    COMMAND = "command"
    INFORMATION = "information"
    WORKFLOW = "workflow"
    DOCUMENT_EXTRACTOR = "document_extractor"
    NOTIFICATION = "notification"
    FORMATTER = "formatter"
    GUI = "gui"


class PluginPermission(StrEnum):
    REGISTER_READ_ONLY_COMMAND = "register_read_only_command"
    REGISTER_GUI_PANEL = "register_gui_panel"
    READ_PLUGIN_CONFIGURATION = "read_plugin_configuration"
    WRITE_PLUGIN_LOCAL_STORAGE = "write_plugin_local_storage"
    READ_SYSTEM_INFORMATION = "read_system_information"
    USE_SAFE_FILE_READ = "use_safe_file_read"
    USE_SAFE_FILE_WRITE = "use_safe_file_write"
    USE_KNOWLEDGE_SEARCH = "use_knowledge_search"
    CREATE_NOTE = "create_note"
    CREATE_TASK = "create_task"
    CREATE_EMAIL_DRAFT = "create_email_draft"
    CREATE_CALENDAR_PROPOSAL = "create_calendar_proposal"
    REGISTER_WORKFLOW_STEP = "register_workflow_step"
    PUBLISH_NOTIFICATION = "publish_notification"
    USE_LOCAL_AI_GENERATION = "use_local_ai_generation"
    USE_LOCAL_AI_EMBEDDINGS = "use_local_ai_embeddings"
    READ_NON_SENSITIVE_PREFERENCES = "read_non_sensitive_preferences"
    REGISTER_PLUGIN_PREFERENCES = "register_plugin_preferences"
    WRITE_PLUGIN_PREFERENCES = "write_plugin_preferences"


class PluginCapability(StrEnum):
    COMMAND_PROVIDER = "command_provider"
    INFORMATION_PROVIDER = "information_provider"
    WORKFLOW_STEP_PROVIDER = "workflow_step_provider"
    DOCUMENT_EXTRACTOR = "document_extractor"
    FORMATTER = "formatter"
    GUI_PANEL = "gui_panel"


class PluginStatus(StrEnum):
    DISCOVERED = "discovered"
    INVALID = "invalid"
    INCOMPATIBLE = "incompatible"
    INSTALLED = "installed"
    DISABLED = "disabled"
    PERMISSION_PENDING = "permission_pending"
    ENABLED = "enabled"
    LOADING = "loading"
    ACTIVE = "active"
    FAILED = "failed"
    QUARANTINED = "quarantined"
    UPDATE_REVIEW_REQUIRED = "update_review_required"
    REMOVED = "removed"


@dataclass(frozen=True, order=True)
class PluginVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> PluginVersion:
        match = _VERSION.fullmatch(value)
        if match is None:
            raise PluginValidationError("Plugin version must use major.minor.patch.")
        return cls(*(int(item) for item in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


PluginApiVersion = PluginVersion
PluginIdentifier = str


@dataclass(frozen=True)
class PluginDependency:
    plugin_id: str
    minimum_version: PluginVersion


@dataclass(frozen=True)
class PluginManifest:
    schema_version: int
    plugin_id: PluginIdentifier
    display_name: str
    version: PluginVersion
    minimum_api_version: PluginApiVersion
    maximum_api_version: PluginApiVersion
    category: PluginCategory
    entry_point: str
    description: str = ""
    publisher: str = ""
    capabilities: tuple[PluginCapability, ...] = ()
    requested_permissions: tuple[PluginPermission, ...] = ()
    supported_operating_systems: tuple[str, ...] = ("windows",)
    minimum_python_version: PluginVersion = field(
        default_factory=lambda: PluginVersion(3, 11, 0)
    )
    extension_points: tuple[str, ...] = ()
    restart_required: bool = False

    def __post_init__(self) -> None:
        for label, value, maximum in (
            ("identifier", self.plugin_id, 100),
            ("display name", self.display_name, 120),
            ("description", self.description, 1_000),
            ("publisher", self.publisher, 200),
            ("entry point", self.entry_point, 120),
        ):
            if not value or len(value) > maximum or _CONTROL.search(value):
                raise PluginValidationError(f"Plugin {label} is invalid.")
        if not _IDENTIFIER.fullmatch(self.plugin_id):
            raise PluginValidationError("Plugin identifier is invalid.")
        if not _ENTRY_POINT.fullmatch(self.entry_point):
            raise PluginValidationError("Plugin entry point is invalid.")
        path = PurePosixPath(self.entry_point.split(":", 1)[0])
        if path.is_absolute() or ".." in path.parts:
            raise PluginValidationError("Plugin entry point must remain relative.")
        if self.schema_version != 1:
            raise PluginValidationError("Plugin manifest schema is unsupported.")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise PluginValidationError("Duplicate plugin capabilities are invalid.")
        if len(set(self.requested_permissions)) != len(self.requested_permissions):
            raise PluginValidationError("Duplicate plugin permissions are invalid.")


@dataclass(frozen=True)
class PluginMetadata:
    manifest: PluginManifest
    source_path: str
    fingerprint: str
    status: PluginStatus = PluginStatus.DISCOVERED
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PluginValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class PluginLoadResult:
    plugin_id: str
    status: PluginStatus
    message: str


@dataclass(frozen=True)
class PluginRegistration:
    plugin_id: str
    extension_points: tuple[str, ...]


@dataclass(frozen=True)
class PluginContext:
    plugin_id: str
    api_version: PluginApiVersion
    approved_permissions: frozenset[PluginPermission]
    configuration: Mapping[str, Any] = field(default_factory=dict)
