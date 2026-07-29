from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from omega.distribution.release import (
    ReleaseValidationError,
    create_build_metadata,
    create_checksums,
    project_version,
    validate_version_sources,
    verify_artifacts,
    write_build_metadata,
)

ROOT = Path(__file__).resolve().parents[2]


def _portable(directory: Path, *names: str) -> Path:
    archive = directory / f"Omega-{project_version(ROOT)}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for name in names or ("OmegaCLI.exe", "Omega.exe", "config/app_config.yaml"):
            bundle.writestr(name, b"safe")
    return archive


def _metadata(directory: Path) -> None:
    metadata = create_build_metadata(
        ROOT,
        now=datetime(2026, 7, 29, 10, 30, tzinfo=UTC),
        environment={"GITHUB_SHA": "a" * 40, "RUNNER_ARCH": "X64"},
    )
    write_build_metadata(metadata, directory / "build-metadata.json")


def test_version_sources_and_release_tag_agree() -> None:
    version = project_version(ROOT)
    assert validate_version_sources(ROOT) == version
    assert validate_version_sources(ROOT, tag=f"v{version}") == version


@pytest.mark.parametrize("tag", ["1.0.0", "v1.0", "v9.9.9", "release-1.0.0"])
def test_invalid_or_mismatched_release_tags_are_rejected(tag: str) -> None:
    with pytest.raises(ReleaseValidationError):
        validate_version_sources(ROOT, tag=tag)


def test_build_metadata_is_bounded_and_utc(tmp_path: Path) -> None:
    metadata = create_build_metadata(
        ROOT,
        now=datetime(2026, 7, 29, 10, 30, tzinfo=UTC),
        environment={"GITHUB_SHA": "a" * 40, "RUNNER_ARCH": "X64"},
    )
    output = tmp_path / "build-metadata.json"
    write_build_metadata(metadata, output)
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["application_version"] == project_version(ROOT)
    assert document["git_commit_sha"] == "a" * 40
    assert document["git_tag"] is None
    assert document["build_timestamp_utc"].endswith("+00:00")
    assert set(document) == {
        "application_version",
        "build_timestamp_utc",
        "git_commit_sha",
        "git_tag",
        "packaging_tool_version",
        "python_version",
        "runner_architecture",
    }


def test_checksum_and_artifact_round_trip(tmp_path: Path) -> None:
    archive = _portable(tmp_path)
    installer = tmp_path / f"Omega-Setup-{project_version(ROOT)}.exe"
    installer.write_bytes(b"installer")
    _metadata(tmp_path)
    create_checksums(tmp_path, tmp_path / "SHA256SUMS.txt")
    assert verify_artifacts(tmp_path) == (archive.name, installer.name)


def test_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    archive = _portable(tmp_path)
    _metadata(tmp_path)
    create_checksums(tmp_path, tmp_path / "SHA256SUMS.txt")
    archive.write_bytes(b"tampered")
    with pytest.raises(ReleaseValidationError, match="checksum"):
        verify_artifacts(tmp_path)


@pytest.mark.parametrize(
    "name",
    [
        "data/omega.db",
        "logs/omega.log",
        "screenshots/private.png",
        "ai_models/model.gguf",
        "plugin_storage/runtime.json",
        "workflow_exports/private.json",
        "../escape.txt",
    ],
)
def test_prohibited_archive_content_is_rejected(tmp_path: Path, name: str) -> None:
    _portable(tmp_path, name)
    _metadata(tmp_path)
    create_checksums(tmp_path, tmp_path / "SHA256SUMS.txt")
    with pytest.raises(ReleaseValidationError, match="archive entry"):
        verify_artifacts(tmp_path)


def test_unexpected_support_file_is_rejected(tmp_path: Path) -> None:
    _portable(tmp_path)
    _metadata(tmp_path)
    (tmp_path / "private-export.json").write_text("{}", encoding="utf-8")
    create_checksums(tmp_path, tmp_path / "SHA256SUMS.txt")
    with pytest.raises(ReleaseValidationError, match="Forbidden artifact"):
        verify_artifacts(tmp_path)


def test_invalid_metadata_is_rejected(tmp_path: Path) -> None:
    _portable(tmp_path)
    _metadata(tmp_path)
    create_checksums(tmp_path, tmp_path / "SHA256SUMS.txt")
    document = json.loads(
        (tmp_path / "build-metadata.json").read_text(encoding="utf-8")
    )
    document["username"] = "private"
    (tmp_path / "build-metadata.json").write_text(
        json.dumps(document), encoding="utf-8"
    )
    with pytest.raises(ReleaseValidationError, match="bounded"):
        verify_artifacts(tmp_path)
