"""Safe application-alias loading and deterministic matching."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from omega.core.exceptions import ConfigurationError
from omega.utils.paths import config_dir


class ApplicationAliasRegistry:
    """Resolve configured aliases to stable canonical application names."""

    def __init__(self, applications: Mapping[str, Sequence[str]]) -> None:
        aliases: dict[str, str] = {}
        for canonical, candidates in applications.items():
            if not canonical or not isinstance(canonical, str) or not candidates:
                raise ConfigurationError(
                    "Application aliases require canonical names and aliases."
                )
            for candidate in candidates:
                if not isinstance(candidate, str) or not candidate.strip():
                    raise ConfigurationError(
                        "Application aliases must be non-empty strings."
                    )
                key = candidate.strip().casefold()
                existing = aliases.get(key)
                if existing is not None:
                    raise ConfigurationError(
                        f"Duplicate or conflicting application alias: {candidate}"
                    )
                aliases[key] = canonical
        self._aliases = aliases
        self._ordered = sorted(aliases, key=len, reverse=True)

    @classmethod
    def from_file(cls, path: Path | None = None) -> ApplicationAliasRegistry:
        """Load aliases from the canonical application-definition JSON file."""
        alias_path = path or config_dir() / "application_aliases.json"
        try:
            data: Any = json.loads(alias_path.read_text(encoding="utf-8"))
            applications = data["applications"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise ConfigurationError(
                f"Invalid application alias configuration: {alias_path}"
            ) from error
        if not isinstance(applications, Mapping):
            raise ConfigurationError("Application aliases must be a JSON object.")
        aliases: dict[str, Sequence[str]] = {}
        for canonical, values in applications.items():
            if isinstance(values, Mapping):
                candidates = values.get("aliases")
            else:
                candidates = values
            if not isinstance(canonical, str) or not isinstance(candidates, Sequence):
                raise ConfigurationError(
                    "Application definitions must contain an aliases list."
                )
            aliases[canonical] = candidates
        return cls(aliases)

    def resolve(self, text: str) -> tuple[str, str] | None:
        """Return canonical and matched alias using strict word boundaries."""
        for alias in self._ordered:
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, re.IGNORECASE):
                return self._aliases[alias], alias
        return None

    @property
    def canonical_names(self) -> tuple[str, ...]:
        return tuple(sorted(set(self._aliases.values())))
