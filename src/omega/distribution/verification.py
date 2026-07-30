"""Bounded distribution-output inspection that never prints secret contents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from omega.core.exceptions import DistributionError

_MAXIMUM_FILES = 25_000
_MAXIMUM_TEXT_SCAN_BYTES = 1_000_000
_PROHIBITED_NAMES = frozenset(
    {
        ".env",
        "credentials.json",
        "oauth.json",
        "token.json",
        "omega.db",
        "omega.log",
    }
)
_PROHIBITED_SUFFIXES = frozenset(
    {
        ".db",
        ".sqlite",
        ".sqlite3",
        ".db-wal",
        ".db-shm",
        ".log",
        ".dmp",
        ".gguf",
        ".safetensors",
        ".onnx",
    }
)
_PROHIBITED_PARTS = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "tests",
        "screenshots",
        "voice_models",
        "ai_models",
        "browser_profiles",
    }
)
_SECRET_ASSIGNMENT = re.compile(
    rb"(?im)^\s*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password)\s*[:=]\s*[^\s#]{8,}"
)
_PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_DEVELOPER_PATH = re.compile(rb"(?i)(?:[a-z]:\\users\\[^\\\r\n]+|e:\\project omega)")


@dataclass(frozen=True, slots=True)
class DistributionVerification:
    files_inspected: int
    prohibited_paths: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.prohibited_paths


def verify_distribution(root: Path) -> DistributionVerification:
    """Inspect one built bundle for private or development artifacts."""

    selected = root.resolve(strict=False)
    if not selected.is_dir():
        raise DistributionError("Distribution directory does not exist.")
    prohibited: list[str] = []
    count = 0
    for path in selected.rglob("*"):
        if not path.is_file():
            continue
        count += 1
        if count > _MAXIMUM_FILES:
            raise DistributionError("Distribution contains too many files to verify.")
        relative = path.relative_to(selected)
        lowered_parts = {part.casefold() for part in relative.parts}
        lowered_name = path.name.casefold()
        unsafe = (
            lowered_name in _PROHIBITED_NAMES
            or any(lowered_name.endswith(suffix) for suffix in _PROHIBITED_SUFFIXES)
            or bool(lowered_parts & _PROHIBITED_PARTS)
            or lowered_name.startswith(".env.")
        )
        if not unsafe and path.stat().st_size <= _MAXIMUM_TEXT_SCAN_BYTES:
            try:
                payload = path.read_bytes()
            except OSError as error:
                raise DistributionError(
                    f"Distribution file could not be inspected: {relative.as_posix()}"
                ) from error
            unsafe = bool(
                _SECRET_ASSIGNMENT.search(payload)
                or _PRIVATE_KEY.search(payload)
                or _DEVELOPER_PATH.search(payload)
            )
        if unsafe:
            prohibited.append(relative.as_posix())
    return DistributionVerification(count, tuple(sorted(prohibited)))


def require_safe_distribution(root: Path) -> DistributionVerification:
    """Return verification or raise with safe path names only."""

    result = verify_distribution(root)
    if not result.passed:
        raise DistributionError(
            "Prohibited distribution files: " + ", ".join(result.prohibited_paths[:25])
        )
    return result
