"""Permission-aware registration of the deliberately small plugin API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from omega.models._serialization import JsonValue, validate_json_value
from omega.plugins.exceptions import PluginPermissionError, PluginValidationError
from omega.plugins.models import PluginPermission


class PluginExtensionPoint(Protocol):
    def shutdown(self) -> None: ...


class PluginCommandProvider(Protocol):
    def commands(self) -> Mapping[str, Callable[[str], JsonValue]]: ...


class PluginInformationProvider(Protocol):
    def information(self, query: str) -> JsonValue: ...


class PluginWorkflowStepProvider(Protocol):
    def workflow_steps(
        self,
    ) -> Mapping[str, Callable[[Mapping[str, JsonValue]], JsonValue]]: ...


class PluginDocumentExtractor(Protocol):
    def extract(self, payload: bytes) -> tuple[str, Mapping[str, JsonValue]]: ...


@dataclass(frozen=True)
class RegisteredCommand:
    plugin_id: str
    name: str
    handler: Callable[[str], JsonValue]


class PluginRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, RegisteredCommand] = {}
        self._workflow_steps: dict[
            str, tuple[str, Callable[[Mapping[str, JsonValue]], JsonValue]]
        ] = {}

    def register_command(
        self,
        plugin_id: str,
        name: str,
        handler: Callable[[str], JsonValue],
        approved: frozenset[PluginPermission],
    ) -> str:
        if PluginPermission.REGISTER_READ_ONLY_COMMAND not in approved:
            raise PluginPermissionError(
                "Read-only command registration is not approved."
            )
        if not name.isidentifier() or name.casefold() in {
            "help",
            "status",
            "confirm",
            "cancel",
            "shutdown",
        }:
            raise PluginValidationError("Plugin command name is protected or invalid.")
        identifier = f"plugin.{plugin_id}.{name}"
        if identifier in self._commands:
            raise PluginValidationError("Plugin command is already registered.")
        self._commands[identifier] = RegisteredCommand(plugin_id, identifier, handler)
        return identifier

    def invoke_command(self, identifier: str, argument: str) -> JsonValue:
        command = self._commands.get(identifier)
        if command is None:
            raise PluginValidationError("Plugin command is not registered.")
        return validate_json_value(command.handler(argument), "plugin command result")

    def register_workflow_step(
        self,
        plugin_id: str,
        name: str,
        handler: Callable[[Mapping[str, JsonValue]], JsonValue],
        approved: frozenset[PluginPermission],
    ) -> str:
        if PluginPermission.REGISTER_WORKFLOW_STEP not in approved:
            raise PluginPermissionError("Workflow-step registration is not approved.")
        if not name.isidentifier() or any(
            word in name.casefold()
            for word in ("shell", "exec", "email_send", "calendar_create")
        ):
            raise PluginValidationError("Plugin workflow step is unsafe or invalid.")
        identifier = f"plugin.{plugin_id}.{name}"
        self._workflow_steps[identifier] = (plugin_id, handler)
        return identifier

    def unregister(self, plugin_id: str) -> None:
        self._commands = {
            key: value
            for key, value in self._commands.items()
            if value.plugin_id != plugin_id
        }
        self._workflow_steps = {
            key: value
            for key, value in self._workflow_steps.items()
            if value[0] != plugin_id
        }
