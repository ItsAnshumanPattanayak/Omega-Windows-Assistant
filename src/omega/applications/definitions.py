"""Typed, data-only definitions for Omega's allowlisted applications."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from omega.core.exceptions import ApplicationRegistryError
from omega.models._serialization import JsonValue, validate_json_mapping

_APPLICATION_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_EXECUTABLE_NAME = re.compile(r"^[A-Za-z0-9_.-]+\.exe$", re.IGNORECASE)
_UNSAFE_TARGET_PARTS = ("..", "&", "|", ";", "<", ">", "\r", "\n", '"')
ALLOWED_APPLICATION_URIS = frozenset({"calculator:", "ms-settings:"})


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ApplicationRegistryError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _string_sequence(value: object, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ApplicationRegistryError(f"{field_name} must be a list of strings.")
    items = tuple(_text(item, field_name) for item in value)
    if len({item.casefold() for item in items}) != len(items):
        raise ApplicationRegistryError(f"{field_name} must not contain duplicates.")
    return items


def _boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ApplicationRegistryError(f"{field_name} must be a boolean.")
    return value


@dataclass(frozen=True)
class ApplicationDefinition:
    """One immutable allowlisted application definition with no execution logic."""

    application_id: str
    display_name: str
    aliases: tuple[str, ...]
    executable_names: tuple[str, ...] = ()
    candidate_paths: tuple[str, ...] = ()
    process_names: tuple[str, ...] = ()
    uri: str | None = None
    validate_process_path: bool = False
    allow_multiple_instances: bool = False
    supports_graceful_close: bool = False
    requires_close_confirmation: bool = True
    allow_force_close: bool = False
    enabled: bool = True
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        application_id = _text(self.application_id, "application_id")
        if not _APPLICATION_ID.fullmatch(application_id):
            raise ApplicationRegistryError(
                "application_id must be a stable lowercase identifier."
            )
        object.__setattr__(self, "application_id", application_id)
        object.__setattr__(
            self, "display_name", _text(self.display_name, "display_name")
        )

        aliases = _string_sequence(self.aliases, "aliases")
        if not aliases:
            raise ApplicationRegistryError("aliases must contain at least one value.")
        object.__setattr__(
            self, "aliases", tuple(alias.casefold() for alias in aliases)
        )

        executable_names = _string_sequence(self.executable_names, "executable_names")
        for name in executable_names:
            if not _EXECUTABLE_NAME.fullmatch(name):
                raise ApplicationRegistryError(
                    f"Unsafe executable name for {application_id}: {name}"
                )
        object.__setattr__(self, "executable_names", executable_names)

        process_names = _string_sequence(self.process_names, "process_names")
        for name in process_names:
            if not _EXECUTABLE_NAME.fullmatch(name):
                raise ApplicationRegistryError(
                    f"Unsafe process name for {application_id}: {name}"
                )
        object.__setattr__(self, "process_names", process_names)

        candidate_paths = _string_sequence(self.candidate_paths, "candidate_paths")
        expected_names = {name.casefold() for name in executable_names}
        for candidate in candidate_paths:
            if any(part in candidate for part in _UNSAFE_TARGET_PARTS):
                raise ApplicationRegistryError(
                    f"Unsafe candidate path for {application_id}."
                )
            candidate_name = re.split(r"[\\/]", candidate)[-1].casefold()
            if candidate_name not in expected_names:
                raise ApplicationRegistryError(
                    f"Candidate path filename is not registered for {application_id}."
                )
        object.__setattr__(self, "candidate_paths", candidate_paths)

        if self.uri is not None:
            uri = _text(self.uri, "uri").casefold()
            if uri not in ALLOWED_APPLICATION_URIS:
                raise ApplicationRegistryError(
                    f"URI target is not allowlisted for {application_id}."
                )
            object.__setattr__(self, "uri", uri)
        if not executable_names and self.uri is None:
            raise ApplicationRegistryError(
                f"{application_id} requires an executable or allowlisted URI."
            )

        for name in (
            "validate_process_path",
            "allow_multiple_instances",
            "supports_graceful_close",
            "requires_close_confirmation",
            "allow_force_close",
            "enabled",
        ):
            _boolean(getattr(self, name), name)
        metadata = validate_json_mapping(self.metadata, "metadata")
        object.__setattr__(self, "metadata", MappingProxyType(metadata))

    @classmethod
    def from_mapping(
        cls, application_id: str, values: Mapping[str, Any]
    ) -> ApplicationDefinition:
        """Build a validated definition from canonical project configuration."""
        try:
            return cls(
                application_id=application_id,
                display_name=values["display_name"],
                aliases=values["aliases"],
                executable_names=values.get("executable_names", ()),
                candidate_paths=values.get("candidate_paths", ()),
                process_names=values.get("process_names", ()),
                uri=values.get("uri"),
                validate_process_path=values.get("validate_process_path", False),
                allow_multiple_instances=values.get("allow_multiple_instances", False),
                supports_graceful_close=values.get("supports_graceful_close", False),
                requires_close_confirmation=values.get(
                    "requires_close_confirmation", True
                ),
                allow_force_close=values.get("allow_force_close", False),
                enabled=values.get("enabled", True),
                metadata=values.get("metadata", {}),
            )
        except KeyError as error:
            raise ApplicationRegistryError(
                f"Application {application_id} is missing {error.args[0]}."
            ) from error

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize the definition without platform handles or services."""
        return {
            "application_id": self.application_id,
            "display_name": self.display_name,
            "aliases": list(self.aliases),
            "executable_names": list(self.executable_names),
            "candidate_paths": list(self.candidate_paths),
            "process_names": list(self.process_names),
            "uri": self.uri,
            "validate_process_path": self.validate_process_path,
            "allow_multiple_instances": self.allow_multiple_instances,
            "supports_graceful_close": self.supports_graceful_close,
            "requires_close_confirmation": self.requires_close_confirmation,
            "allow_force_close": self.allow_force_close,
            "enabled": self.enabled,
            "metadata": dict(self.metadata),
        }
