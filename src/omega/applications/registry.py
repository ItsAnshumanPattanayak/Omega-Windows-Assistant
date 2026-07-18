"""Canonical allowlisted application registry."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from omega.applications.definitions import ApplicationDefinition
from omega.core.exceptions import ApplicationRegistryError
from omega.utils.paths import config_dir


class ApplicationRegistry:
    """Validate and resolve only project-defined application identifiers."""

    def __init__(self, definitions: Iterable[ApplicationDefinition]) -> None:
        by_id: dict[str, ApplicationDefinition] = {}
        by_alias: dict[str, ApplicationDefinition] = {}
        for definition in definitions:
            if not isinstance(definition, ApplicationDefinition):
                raise ApplicationRegistryError(
                    "Registry entries must be ApplicationDefinition values."
                )
            if definition.application_id in by_id:
                raise ApplicationRegistryError(
                    f"Duplicate application ID: {definition.application_id}"
                )
            by_id[definition.application_id] = definition
            for alias in definition.aliases:
                key = alias.casefold()
                if key in by_alias:
                    raise ApplicationRegistryError(
                        f"Conflicting application alias: {alias}"
                    )
                by_alias[key] = definition
        if not by_id:
            raise ApplicationRegistryError("Application registry must not be empty.")
        self._by_id = by_id
        self._by_alias = by_alias

    @classmethod
    def from_file(cls, path: Path | None = None) -> ApplicationRegistry:
        """Load the canonical application registry JSON file."""
        registry_path = path or config_dir() / "application_aliases.json"
        try:
            data: Any = json.loads(registry_path.read_text(encoding="utf-8"))
            raw_applications = data["applications"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise ApplicationRegistryError(
                f"Invalid application registry configuration: {registry_path}"
            ) from error
        if not isinstance(raw_applications, Mapping):
            raise ApplicationRegistryError("Applications must be a JSON object.")
        definitions: list[ApplicationDefinition] = []
        for application_id, values in raw_applications.items():
            if not isinstance(application_id, str) or not isinstance(values, Mapping):
                raise ApplicationRegistryError(
                    "Application registry entries must be named JSON objects."
                )
            definitions.append(
                ApplicationDefinition.from_mapping(application_id, values)
            )
        return cls(definitions)

    @property
    def definitions(self) -> tuple[ApplicationDefinition, ...]:
        """Return an immutable snapshot of every definition, including disabled ones."""
        return tuple(self._by_id.values())

    def get(
        self, application_id: str, *, include_disabled: bool = False
    ) -> ApplicationDefinition | None:
        """Look up an exact canonical ID without accepting paths or arguments."""
        definition = self._by_id.get(application_id.casefold())
        if definition is None or (not include_disabled and not definition.enabled):
            return None
        return definition

    def resolve(
        self, identifier: str, *, include_disabled: bool = False
    ) -> ApplicationDefinition | None:
        """Resolve an exact canonical ID or configured alias."""
        key = identifier.strip().casefold()
        definition = self._by_id.get(key) or self._by_alias.get(key)
        if definition is None or (not include_disabled and not definition.enabled):
            return None
        return definition
