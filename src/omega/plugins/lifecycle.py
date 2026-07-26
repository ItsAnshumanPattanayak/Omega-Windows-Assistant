"""Lazy, approved same-process loading with bounded failure containment."""

from __future__ import annotations

import importlib.util
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from typing import Any

from omega.plugins.configuration import PluginConfiguration
from omega.plugins.exceptions import PluginLoadError
from omega.plugins.models import (
    PluginContext,
    PluginLoadResult,
    PluginMetadata,
    PluginStatus,
)
from omega.plugins.validation import PluginValidator


class PluginLoader:
    def __init__(
        self, configuration: PluginConfiguration, validator: PluginValidator
    ) -> None:
        self.configuration = configuration
        self.validator = validator

    def load(
        self, metadata: PluginMetadata, context: PluginContext
    ) -> tuple[PluginLoadResult, Any]:
        if metadata.status is not PluginStatus.ENABLED:
            raise PluginLoadError("Only an enabled reviewed plugin may be loaded.")
        root = Path(metadata.source_path).resolve(strict=True)
        if self.validator.fingerprint(root) != metadata.fingerprint:
            raise PluginLoadError("Plugin fingerprint changed and requires review.")
        module_name, function_name = metadata.manifest.entry_point.split(":", 1)
        source = (root / f"{module_name}.py").resolve(strict=True)
        if source.parent != root or source.is_symlink():
            raise PluginLoadError("Plugin entry point escapes its approved package.")
        unique_name = (
            f"omega_reviewed_plugin_{metadata.manifest.plugin_id.replace('-', '_')}"
        )
        specification = importlib.util.spec_from_file_location(unique_name, source)
        if specification is None or specification.loader is None:
            raise PluginLoadError("Plugin entry point could not be prepared.")
        module = importlib.util.module_from_spec(specification)
        try:
            specification.loader.exec_module(module)
            factory = getattr(module, function_name)
            instance = self._bounded(
                factory, context, self.configuration.plugin_call_timeout_seconds
            )
        except Exception as error:
            raise PluginLoadError(
                "Plugin failed during bounded initialization."
            ) from error
        return (
            PluginLoadResult(
                metadata.manifest.plugin_id, PluginStatus.ACTIVE, "Plugin activated."
            ),
            instance,
        )

    @staticmethod
    def _bounded(callable_value: Any, argument: Any, timeout: int) -> Any:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="omega-plugin")
        future = executor.submit(callable_value, argument)
        try:
            return future.result(timeout=timeout)
        except TimeoutError as error:
            future.cancel()
            raise PluginLoadError("Plugin call exceeded its timeout.") from error
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


class PluginLifecycle:
    def __init__(
        self, configuration: PluginConfiguration, loader: PluginLoader
    ) -> None:
        self.configuration = configuration
        self.loader = loader
        self._active: dict[str, Any] = {}

    def activate(
        self, metadata: PluginMetadata, context: PluginContext
    ) -> PluginLoadResult:
        if metadata.manifest.plugin_id in self._active:
            raise PluginLoadError("Plugin is already active.")
        result, instance = self.loader.load(metadata, context)
        self._active[metadata.manifest.plugin_id] = instance
        return result

    def deactivate(self, plugin_id: str) -> None:
        instance = self._active.pop(plugin_id, None)
        if instance is None:
            return
        shutdown = getattr(instance, "shutdown", None)
        if callable(shutdown):
            PluginLoader._bounded(
                lambda _: shutdown(),
                None,
                self.configuration.plugin_shutdown_timeout_seconds,
            )

    def instance(self, plugin_id: str) -> Any:
        instance = self._active.get(plugin_id)
        if instance is None:
            raise PluginLoadError("Plugin is not active.")
        return instance

    def shutdown(self) -> None:
        for plugin_id in tuple(self._active):
            try:
                self.deactivate(plugin_id)
            except PluginLoadError:
                continue
