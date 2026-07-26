"""Bounded JSON-only per-plugin local storage."""

import json
from pathlib import Path

from omega.models._serialization import JsonValue, validate_json_value
from omega.plugins.exceptions import PluginStorageError


class PluginLocalStorage:
    def __init__(self, root: Path, plugin_id: str, maximum_bytes: int) -> None:
        if any(part in plugin_id for part in ("/", "\\", "..")):
            raise PluginStorageError("Plugin storage identifier is invalid.")
        self.root = root.resolve(strict=False)
        self.directory = (self.root / plugin_id).resolve(strict=False)
        if self.directory.parent != self.root:
            raise PluginStorageError("Plugin storage path escapes its namespace.")
        self.maximum_bytes = maximum_bytes

    def write(self, key: str, value: JsonValue) -> None:
        target = self._target(key)
        payload = json.dumps(
            validate_json_value(value, "plugin storage"), sort_keys=True
        ).encode()
        if len(payload) > self.maximum_bytes:
            raise PluginStorageError("Plugin storage value exceeds its limit.")
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.directory.is_symlink():
            raise PluginStorageError("Plugin storage namespace is unsafe.")
        existing = sum(
            item.stat().st_size
            for item in self.directory.glob("*.json")
            if item != target
        )
        if existing + len(payload) > self.maximum_bytes:
            raise PluginStorageError("Plugin storage quota exceeded.")
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(target)

    def read(self, key: str) -> JsonValue:
        target = self._target(key)
        try:
            return validate_json_value(
                json.loads(target.read_bytes()), "plugin storage"
            )
        except (OSError, json.JSONDecodeError) as error:
            raise PluginStorageError("Plugin storage value is unavailable.") from error

    def _target(self, key: str) -> Path:
        if not key or len(key) > 64 or not key.replace("_", "").isalnum():
            raise PluginStorageError("Plugin storage key is invalid.")
        target = (self.directory / f"{key}.json").resolve(strict=False)
        if target.parent != self.directory:
            raise PluginStorageError("Plugin storage path escapes its namespace.")
        return target
