"""Resolution of registered logical user locations without directory creation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from omega.core.exceptions import FileLocationError
from omega.files.definitions import LOCATION_ALIASES, LOGICAL_LOCATIONS
from omega.files.results import ResolvedLocation

_DISPLAY_NAMES = {
    "desktop": "Desktop",
    "documents": "Documents",
    "downloads": "Downloads",
    "pictures": "Pictures",
    "music": "Music",
    "videos": "Videos",
    "home": "Home",
    "current_directory": "current directory",
}


class FileLocationResolver:
    """Resolve only approved logical locations to stable absolute directories."""

    def __init__(
        self,
        roots: Mapping[str, Path] | None = None,
        *,
        startup_directory: Path | None = None,
    ) -> None:
        if roots is None:
            home = Path.home().resolve(strict=False)
            startup = (startup_directory or Path.cwd()).resolve(strict=False)
            supplied = {
                "desktop": home / "Desktop",
                "documents": home / "Documents",
                "downloads": home / "Downloads",
                "pictures": home / "Pictures",
                "music": home / "Music",
                "videos": home / "Videos",
                "home": home,
                "current_directory": startup,
            }
        else:
            supplied = dict(roots)
        unknown = set(supplied).difference(LOGICAL_LOCATIONS)
        if unknown:
            raise FileLocationError(
                f"Unknown logical location(s): {', '.join(sorted(unknown))}."
            )
        self._roots = {
            name: Path(root).expanduser().resolve(strict=False)
            for name, root in supplied.items()
        }
        self._cache: dict[str, ResolvedLocation] = {}

    @staticmethod
    def canonical_name(value: str) -> str:
        """Return the registered name for a safe user-facing location alias."""
        normalized = " ".join(value.strip().casefold().split())
        canonical = LOCATION_ALIASES.get(normalized)
        if canonical is None:
            raise FileLocationError("That file location is not approved.")
        return canonical

    def resolve(self, value: str) -> ResolvedLocation:
        """Resolve an existing logical directory or report it as unavailable."""
        canonical = self.canonical_name(value)
        cached = self._cache.get(canonical)
        if cached is not None:
            return cached
        root = self._roots.get(canonical)
        if root is None or not root.exists() or not root.is_dir():
            raise FileLocationError(f"The {canonical} location is unavailable.")
        resolved = ResolvedLocation(
            canonical, _DISPLAY_NAMES[canonical], root.resolve()
        )
        self._cache[canonical] = resolved
        return resolved

    @property
    def registered_locations(self) -> tuple[str, ...]:
        """Return logical names configured for this resolver instance."""
        return tuple(name for name in LOGICAL_LOCATIONS if name in self._roots)
