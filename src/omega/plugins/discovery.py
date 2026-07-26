"""Manifest-only discovery from explicitly approved plugin roots."""

from __future__ import annotations

from pathlib import Path

from omega.plugins.configuration import PluginConfiguration
from omega.plugins.exceptions import PluginValidationError
from omega.plugins.models import PluginMetadata, PluginStatus
from omega.plugins.validation import PluginValidator


class PluginDiscovery:
    def __init__(
        self,
        configuration: PluginConfiguration,
        validator: PluginValidator,
        approved_roots: tuple[Path, ...],
    ) -> None:
        self.configuration = configuration
        self.validator = validator
        self.approved_roots = tuple(
            root.resolve(strict=False) for root in approved_roots
        )

    def discover(self) -> tuple[PluginMetadata, ...]:
        if not self.configuration.enabled:
            return ()
        discovered: list[PluginMetadata] = []
        identifiers: set[str] = set()
        for root in self.approved_roots:
            if not root.is_dir() or root.is_symlink():
                continue
            for directory in sorted(
                root.iterdir(), key=lambda item: item.name.casefold()
            ):
                if len(discovered) >= self.configuration.maximum_plugins:
                    return tuple(discovered)
                if (
                    directory.name.startswith(".")
                    or directory.is_symlink()
                    or not directory.is_dir()
                ):
                    continue
                resolved = directory.resolve(strict=True)
                if resolved.parent != root:
                    continue
                manifest = self.validator.parse_file(resolved / "plugin.json")
                if manifest.plugin_id in identifiers:
                    raise PluginValidationError(
                        "Duplicate plugin identifier discovered."
                    )
                identifiers.add(manifest.plugin_id)
                compatibility = self.validator.validate_compatibility(manifest)
                discovered.append(
                    PluginMetadata(
                        manifest,
                        str(resolved),
                        self.validator.fingerprint(resolved),
                        (
                            PluginStatus.DISCOVERED
                            if compatibility.valid
                            else PluginStatus.INCOMPATIBLE
                        ),
                    )
                )
        return tuple(discovered)
