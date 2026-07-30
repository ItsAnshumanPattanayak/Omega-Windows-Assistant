"""Development and frozen resource resolution for Omega V2 assets."""

from __future__ import annotations

from pathlib import Path

from omega.core.exceptions import GuiError
from omega.utils.paths import resource_root


class GuiAssetError(GuiError):
    """Raised when a configured GUI asset escapes the resource root."""


def resolve_gui_asset(relative_path: str, *, root: Path | None = None) -> Path:
    """Resolve a safe relative resource path without requiring it to exist."""

    base = (root or resource_root()).resolve(strict=False)
    relative = Path(relative_path.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise GuiAssetError("The GUI asset path must remain under the resource root.")
    selected = (base / relative).resolve(strict=False)
    try:
        selected.relative_to(base)
    except ValueError as error:
        raise GuiAssetError(
            "The GUI asset path must remain under the resource root."
        ) from error
    return selected
