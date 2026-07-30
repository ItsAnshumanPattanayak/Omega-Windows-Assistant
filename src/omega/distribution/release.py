"""Deterministic, bounded release metadata and artifact validation utilities."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tomllib
import zipfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path, PurePosixPath
from typing import Final

from omega.core.exceptions import DistributionError
from omega.distribution.metadata import APPLICATION_METADATA
from omega.utils.constants import APP_VERSION

_VERSION_PATTERN: Final = re.compile(r"^\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?$")
_TAG_PATTERN: Final = re.compile(
    r"^v(?P<version>\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?)$"
)
_SHA_PATTERN: Final = re.compile(r"^[0-9a-f]{64}  ([A-Za-z0-9][A-Za-z0-9._-]*)$")
_DISTRIBUTABLE_SUFFIXES: Final = frozenset({".exe", ".zip"})
_ALLOWED_SUPPORT_FILES: Final = frozenset({"SHA256SUMS.txt", "build-metadata.json"})
_FORBIDDEN_ARCHIVE_PARTS: Final = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "tests",
        "data",
        "logs",
        "screenshots",
        "voice_models",
        "ai_models",
        "browser_profiles",
        "plugin_storage",
        "plugin_runtime",
        "user_plugins",
        "profile_exports",
        "workflow_exports",
        "schedule_exports",
        "knowledge_exports",
        "productivity_exports",
        "clipboard_history",
    }
)
_FORBIDDEN_ARCHIVE_SUFFIXES: Final = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-wal",
    ".db-shm",
    ".log",
    ".dmp",
    ".gguf",
    ".onnx",
    ".safetensors",
    ".pem",
    ".key",
)


class ReleaseValidationError(DistributionError):
    """Raised when local release inputs violate the bounded release contract."""


@dataclass(frozen=True, slots=True)
class BuildMetadata:
    """Non-sensitive metadata recorded beside distributable artifacts."""

    application_version: str
    git_commit_sha: str
    git_tag: str | None
    build_timestamp_utc: str
    python_version: str
    runner_architecture: str
    packaging_tool_version: str


def project_version(repository_root: Path) -> str:
    """Read the authoritative project version from ``pyproject.toml``."""

    path = repository_root.resolve() / "pyproject.toml"
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
        value = document["project"]["version"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise ReleaseValidationError(
            "pyproject.toml has no valid project version."
        ) from error
    if not isinstance(value, str) or not _VERSION_PATTERN.fullmatch(value):
        raise ReleaseValidationError(
            "The project version is not a supported release version."
        )
    return value


def validate_version_sources(repository_root: Path, *, tag: str | None = None) -> str:
    """Require project, runtime, packaging, installer, and optional tag agreement."""

    root = repository_root.resolve()
    expected = project_version(root)
    if APP_VERSION != expected or APPLICATION_METADATA.version != expected:
        raise ReleaseValidationError(
            "Project, runtime, and distribution versions differ."
        )
    spec = _read_required(root / "packaging" / "omega.spec")
    installer = _read_required(root / "installer" / "omega.iss")
    if "APPLICATION_METADATA.version" not in spec:
        raise ReleaseValidationError(
            "The packaging spec does not use application metadata."
        )
    if "AppVersion={#MyAppVersion}" not in installer:
        raise ReleaseValidationError(
            "The installer does not use the supplied application version."
        )
    if tag is not None:
        match = _TAG_PATTERN.fullmatch(tag)
        if match is None or match.group("version") != expected:
            raise ReleaseValidationError(
                "The release tag does not match the project version."
            )
    return expected


def create_build_metadata(
    repository_root: Path,
    *,
    now: datetime | None = None,
    environment: dict[str, str] | None = None,
) -> BuildMetadata:
    """Create bounded metadata without usernames or environment dumps."""

    root = repository_root.resolve()
    version = validate_version_sources(root)
    values = os.environ if environment is None else environment
    commit = values.get("GITHUB_SHA") or _git_output(root, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise ReleaseValidationError("The Git commit SHA is invalid.")
    tag_value = (
        values.get("GITHUB_REF_NAME")
        if values.get("GITHUB_REF_TYPE") == "tag"
        else None
    )
    if tag_value is not None:
        validate_version_sources(root, tag=tag_value)
    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ReleaseValidationError("Build timestamps must be timezone-aware.")
    try:
        packager = package_version("pyinstaller")
    except PackageNotFoundError:
        packager = "not-installed"
    architecture = values.get("RUNNER_ARCH") or platform.machine() or "unknown"
    return BuildMetadata(
        application_version=version,
        git_commit_sha=commit.lower(),
        git_tag=tag_value,
        build_timestamp_utc=timestamp.astimezone(UTC).isoformat(),
        python_version=platform.python_version(),
        runner_architecture=architecture,
        packaging_tool_version=packager,
    )


def write_build_metadata(metadata: BuildMetadata, output: Path) -> None:
    """Write one stable UTF-8 JSON metadata document."""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(asdict(metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def create_checksums(directory: Path, output: Path) -> tuple[str, ...]:
    """Hash only final ZIP and EXE distributables in one artifact directory."""

    root = directory.resolve(strict=True)
    selected = _distributables(root)
    if not selected:
        raise ReleaseValidationError("No distributable artifacts were found.")
    lines = tuple(f"{_sha256(path)}  {path.name}" for path in selected)
    if output.resolve(strict=False).parent != root:
        raise ReleaseValidationError(
            "The checksum manifest must remain in the artifact directory."
        )
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    return lines


def verify_artifacts(directory: Path) -> tuple[str, ...]:
    """Verify bounded names, archives, and a complete SHA-256 manifest."""

    root = directory.resolve(strict=True)
    distributables = _distributables(root)
    portable_name = f"Omega-{APP_VERSION}-windows-x64.zip"
    allowed_distributables = {
        portable_name,
        f"Omega-Windows-Assistant-Setup-v{APP_VERSION}.exe",
    }
    if portable_name not in {path.name for path in distributables}:
        raise ReleaseValidationError(
            "The versioned Windows x64 portable archive is missing."
        )
    if any(path.name not in allowed_distributables for path in distributables):
        raise ReleaseValidationError(
            "The artifact directory contains an unexpected distributable."
        )
    for child in root.iterdir():
        if not child.is_file():
            raise ReleaseValidationError(f"Unexpected artifact entry: {child.name}")
        if child not in distributables and child.name not in _ALLOWED_SUPPORT_FILES:
            raise ReleaseValidationError(f"Forbidden artifact file: {child.name}")
    manifest = root / "SHA256SUMS.txt"
    if not manifest.is_file():
        raise ReleaseValidationError("SHA256SUMS.txt is missing.")
    expected = {path.name: _sha256(path) for path in distributables}
    actual: dict[str, str] = {}
    for line in manifest.read_text(encoding="ascii").splitlines():
        match = _SHA_PATTERN.fullmatch(line)
        if match is None:
            raise ReleaseValidationError(
                "The checksum manifest contains an invalid entry."
            )
        name = match.group(1)
        if name in actual:
            raise ReleaseValidationError(
                "The checksum manifest contains a duplicate entry."
            )
        actual[name] = line[:64]
    if actual != expected:
        raise ReleaseValidationError(
            "The checksum manifest does not match final artifacts."
        )
    for archive in (
        path for path in distributables if path.suffix.casefold() == ".zip"
    ):
        _verify_archive(archive)
    _verify_metadata(root / "build-metadata.json")
    return tuple(path.name for path in distributables)


def _verify_archive(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) > 25_000:
                raise ReleaseValidationError(
                    "The portable archive contains too many entries."
                )
            for name in names:
                item = PurePosixPath(name.replace("\\", "/"))
                lowered_parts = {part.casefold() for part in item.parts}
                lowered = item.name.casefold()
                if (
                    item.is_absolute()
                    or ".." in item.parts
                    or bool(lowered_parts & _FORBIDDEN_ARCHIVE_PARTS)
                    or lowered.startswith(".env")
                    or lowered.endswith(_FORBIDDEN_ARCHIVE_SUFFIXES)
                ):
                    raise ReleaseValidationError(
                        f"Forbidden archive entry: {item.name}"
                    )
            expected_executables = {"Omega.exe", "OmegaCLI.exe"}
            archive_files = {
                PurePosixPath(name.replace("\\", "/")).name for name in names
            }
            if not expected_executables.issubset(archive_files):
                raise ReleaseValidationError(
                    "The portable archive is missing Omega executables."
                )
    except (OSError, zipfile.BadZipFile) as error:
        raise ReleaseValidationError("A portable archive is unreadable.") from error


def _verify_metadata(path: Path) -> None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseValidationError(
            "Bounded build metadata is missing or invalid."
        ) from error
    expected_fields = {
        "application_version",
        "git_commit_sha",
        "git_tag",
        "build_timestamp_utc",
        "python_version",
        "runner_architecture",
        "packaging_tool_version",
    }
    if not isinstance(document, dict) or set(document) != expected_fields:
        raise ReleaseValidationError("Build metadata fields are not bounded.")
    if document["application_version"] != APP_VERSION:
        raise ReleaseValidationError("Build metadata version does not match Omega.")
    commit = document["git_commit_sha"]
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ReleaseValidationError("Build metadata commit SHA is invalid.")
    tag = document["git_tag"]
    if tag is not None:
        if not isinstance(tag, str):
            raise ReleaseValidationError("Build metadata tag is invalid.")
        match = _TAG_PATTERN.fullmatch(tag)
        if match is None or match.group("version") != APP_VERSION:
            raise ReleaseValidationError("Build metadata tag does not match Omega.")
    timestamp = document["build_timestamp_utc"]
    try:
        parsed = (
            datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else None
        )
    except ValueError as error:
        raise ReleaseValidationError("Build metadata timestamp is invalid.") from error
    if (
        parsed is None
        or parsed.tzinfo is None
        or parsed.utcoffset() != UTC.utcoffset(parsed)
    ):
        raise ReleaseValidationError("Build metadata timestamp is not UTC-aware.")
    for field in ("python_version", "runner_architecture", "packaging_tool_version"):
        value = document[field]
        if not isinstance(value, str) or not value or len(value) > 100:
            raise ReleaseValidationError(f"Build metadata {field} is invalid.")


def _distributables(root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                path
                for path in root.iterdir()
                if path.is_file() and path.suffix.casefold() in _DISTRIBUTABLE_SUFFIXES
            ),
            key=lambda path: path.name.casefold(),
        )
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_required(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReleaseValidationError(
            f"Required release source is missing: {path.name}"
        ) from error


def _git_output(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ReleaseValidationError("Git metadata could not be read.") from error
    return result.stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Omega release inputs and artifacts"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    version_parser = subparsers.add_parser("validate-version")
    version_parser.add_argument("--repository-root", type=Path, required=True)
    version_parser.add_argument("--tag")
    metadata_parser = subparsers.add_parser("create-metadata")
    metadata_parser.add_argument("--repository-root", type=Path, required=True)
    metadata_parser.add_argument("--output", type=Path, required=True)
    checksums_parser = subparsers.add_parser("create-checksums")
    checksums_parser.add_argument("--directory", type=Path, required=True)
    checksums_parser.add_argument("--output", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify-artifacts")
    verify_parser.add_argument("--directory", type=Path, required=True)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the local release validator without publishing or mutating Git."""

    values = _parser().parse_args(arguments)
    try:
        if values.command == "validate-version":
            validated = validate_version_sources(values.repository_root, tag=values.tag)
            print(f"Omega version validation passed: {validated}")
        elif values.command == "create-metadata":
            write_build_metadata(
                create_build_metadata(values.repository_root), values.output
            )
            print(f"Build metadata written: {values.output.name}")
        elif values.command == "create-checksums":
            created = create_checksums(values.directory, values.output)
            print(f"Checksum manifest written for {len(created)} artifact(s).")
        else:
            verified = verify_artifacts(values.directory)
            print(
                "Release artifact verification passed: "
                f"{len(verified)} distributable(s)."
            )
    except (OSError, ReleaseValidationError) as error:
        print(f"Omega release validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
