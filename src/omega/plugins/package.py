"""Side-effect-free package inspection and atomic reviewed installation."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from omega.plugins.configuration import PluginConfiguration
from omega.plugins.exceptions import PluginValidationError
from omega.plugins.models import PluginManifest
from omega.plugins.validation import PluginValidator

_BLOCKED_SUFFIXES = {
    ".exe",
    ".dll",
    ".pyd",
    ".com",
    ".msi",
    ".bat",
    ".cmd",
    ".ps1",
    ".sh",
}
_BLOCKED_NAMES = {
    "setup.py",
    "pyproject.toml",
    "requirements.txt",
    ".pth",
    "autorun.inf",
}
_CREDENTIAL_WORDS = ("credential", "password", "secret", "private_key", "access_token")
_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


class PluginPackageInstaller:
    def __init__(
        self,
        configuration: PluginConfiguration,
        validator: PluginValidator,
        install_root: Path,
    ) -> None:
        self.configuration = configuration
        self.validator = validator
        self.install_root = install_root.resolve(strict=False)

    def validate(self, package: Path) -> PluginManifest:
        if (
            package.is_symlink()
            or not package.is_file()
            or package.suffix.casefold() != ".zip"
        ):
            raise PluginValidationError(
                "Plugin package must be an explicitly selected ZIP file."
            )
        if package.stat().st_size > self.configuration.maximum_package_bytes:
            raise PluginValidationError("Plugin package exceeds the size limit.")
        try:
            with zipfile.ZipFile(package) as archive:
                files = archive.infolist()
                if len(files) > self.configuration.maximum_package_files:
                    raise PluginValidationError(
                        "Plugin package contains too many files."
                    )
                total = 0
                for info in files:
                    self._validate_member(info)
                    total += info.file_size
                    if total > self.configuration.maximum_package_bytes:
                        raise PluginValidationError(
                            "Expanded plugin package exceeds the size limit."
                        )
                try:
                    payload = archive.read("plugin.json")
                except KeyError as error:
                    raise PluginValidationError(
                        "Plugin package has no root manifest."
                    ) from error
        except zipfile.BadZipFile as error:
            raise PluginValidationError(
                "Plugin package is not a valid ZIP archive."
            ) from error
        return self.validator.parse(payload)

    def install(self, package: Path) -> tuple[PluginManifest, Path]:
        manifest = self.validate(package)
        self.validator.require_compatible(manifest)
        self.install_root.mkdir(parents=True, exist_ok=True)
        destination = self.install_root / manifest.plugin_id
        if destination.exists():
            raise PluginValidationError(
                "Plugin is already installed; updates require review."
            )
        with tempfile.TemporaryDirectory(
            prefix="omega-plugin-", dir=self.install_root
        ) as staging_name:
            staging = Path(staging_name)
            with zipfile.ZipFile(package) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    target = (staging / PurePosixPath(info.filename)).resolve(
                        strict=False
                    )
                    if staging not in target.parents:
                        raise PluginValidationError(
                            "Plugin package path escapes its staging directory."
                        )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
            os.replace(staging, destination)
            return manifest, destination

    @staticmethod
    def _validate_member(info: zipfile.ZipInfo) -> None:
        name = info.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise PluginValidationError("Plugin package contains an unsafe path.")
        if name.startswith(("/", "\\")) or (len(name) > 1 and name[1] == ":"):
            raise PluginValidationError("Plugin package contains an absolute path.")
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise PluginValidationError("Plugin package contains a symbolic link.")
        for part in path.parts:
            stem = part.split(".", 1)[0].casefold()
            if stem in _WINDOWS_RESERVED or "\x00" in part:
                raise PluginValidationError(
                    "Plugin package contains an unsafe Windows name."
                )
        leaf = path.name.casefold()
        if path.suffix.casefold() in _BLOCKED_SUFFIXES or leaf in _BLOCKED_NAMES:
            raise PluginValidationError(
                "Plugin package contains executable or install-hook content."
            )
        if any(word in leaf for word in _CREDENTIAL_WORDS):
            raise PluginValidationError(
                "Plugin package contains credential-like content."
            )
