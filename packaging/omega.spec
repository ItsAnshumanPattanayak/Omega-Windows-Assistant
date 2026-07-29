# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 6.21 one-folder build for Omega CLI and GUI executables."""

from pathlib import Path
import sys

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from omega.distribution.metadata import APPLICATION_METADATA

version_parts = tuple(int(item) for item in APPLICATION_METADATA.version.split("."))
file_version = (*version_parts, *(0 for _ in range(4 - len(version_parts))))
version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=file_version,
        prodvers=file_version,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", APPLICATION_METADATA.publisher),
                        StringStruct("FileDescription", APPLICATION_METADATA.description),
                        StringStruct("FileVersion", APPLICATION_METADATA.version),
                        StringStruct("InternalName", "Omega"),
                        StringStruct("LegalCopyright", "Copyright Omega contributors"),
                        StringStruct("ProductName", APPLICATION_METADATA.name),
                        StringStruct("ProductVersion", APPLICATION_METADATA.version),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

datas = [
    (str(ROOT / "packaging" / "defaults" / "app_config.yaml"), "config"),
    (str(ROOT / "config" / "application_aliases.json"), "config"),
    (str(ROOT / "config" / "command_patterns.json"), "config"),
    (str(ROOT / "config" / "permissions.json"), "config"),
    (str(ROOT / "config" / "protected_paths.json"), "config"),
    (str(ROOT / "docs" / "installation.md"), "docs"),
    (str(ROOT / "docs" / "security.md"), "docs"),
    (str(ROOT / "LICENSE"), "."),
]

hidden_imports = [
    "omega.gui.application",
    "omega.performance.diagnostics",
    "omega.security.diagnostics",
    "omega.voice.microphone",
    "omega.voice.recognizer",
    "omega.voice.service",
    "omega.voice.speaker",
    "omega.voice.terminal",
]

analysis = Analysis(
    [str(ROOT / "packaging" / "entrypoint.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["black", "mypy", "pytest", "ruff", "tests"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

cli = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="OmegaCLI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    version=version_info,
    contents_directory="_internal",
)
gui = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Omega",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    version=version_info,
    contents_directory="_internal",
)

bundle = COLLECT(
    cli,
    gui,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="Omega",
)
