import json
import stat
import zipfile
from pathlib import Path

import pytest

from omega.plugins import PluginConfiguration, PluginPackageInstaller, PluginValidator
from omega.plugins.exceptions import PluginValidationError


def package(
    tmp_path: Path, manifest: dict[str, object], members: dict[str, bytes] | None = None
) -> Path:
    target = tmp_path / "plugin.zip"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("plugin.json", json.dumps(manifest))
        archive.writestr("plugin.py", b"def create_plugin(context): return object()")
        for name, payload in (members or {}).items():
            archive.writestr(name, payload)
    return target


def installer(tmp_path: Path, **settings: object) -> PluginPackageInstaller:
    config = PluginConfiguration.from_mapping(settings)
    return PluginPackageInstaller(
        config, PluginValidator(config), tmp_path / "installed"
    )


def test_valid_package_installs_atomically_and_disabled_policy_is_external(
    tmp_path: Path, manifest_data: dict[str, object]
) -> None:
    value = installer(tmp_path)
    manifest, destination = value.install(package(tmp_path, manifest_data))
    assert manifest.plugin_id == "example.readonly"
    assert destination.is_dir() and (destination / "plugin.json").is_file()


@pytest.mark.parametrize(
    "name",
    [
        "../escape.py",
        "/absolute.py",
        "C:/absolute.py",
        "CON.txt",
        "setup.py",
        "tool.exe",
        "secret_token.txt",
        "hooks.ps1",
    ],
)
def test_unsafe_archive_member_rejected(
    tmp_path: Path, manifest_data: dict[str, object], name: str
) -> None:
    value = installer(tmp_path)
    with pytest.raises(PluginValidationError):
        value.validate(package(tmp_path, manifest_data, {name: b"inert"}))


def test_symlink_archive_member_rejected(
    tmp_path: Path, manifest_data: dict[str, object]
) -> None:
    target = tmp_path / "plugin.zip"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("plugin.json", json.dumps(manifest_data))
        info = zipfile.ZipInfo("linked.py")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "target.py")
    with pytest.raises(PluginValidationError):
        installer(tmp_path).validate(target)


def test_package_count_and_expanded_size_bounds(
    tmp_path: Path, manifest_data: dict[str, object]
) -> None:
    with pytest.raises(PluginValidationError):
        installer(tmp_path, maximum_package_files=2).validate(
            package(tmp_path, manifest_data, {"one.txt": b"1"})
        )
    with pytest.raises(PluginValidationError):
        installer(tmp_path, maximum_package_bytes=500).validate(
            package(tmp_path, manifest_data, {"large.txt": b"x" * 1_000})
        )


def test_validation_never_imports_or_runs_setup(
    tmp_path: Path, manifest_data: dict[str, object]
) -> None:
    marker = tmp_path / "ran.txt"
    payload = (
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')".encode()
    )
    value = installer(tmp_path)
    value.validate(package(tmp_path, manifest_data, {"inert.txt": payload}))
    assert not marker.exists()
