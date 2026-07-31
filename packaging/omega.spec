# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 6.21 one-folder build for Omega CLI and GUI executables."""

from pathlib import Path
import sys

SPEC_FILE = Path(SPEC).resolve(strict=True)
PACKAGING_ROOT = SPEC_FILE.parent
ROOT = PACKAGING_ROOT.parent.resolve(strict=True)
SOURCE_ROOT = (ROOT / "src").resolve(strict=True)
ENTRYPOINT = (PACKAGING_ROOT / "entrypoint.py").resolve(strict=True)


def source_path(*parts: str) -> str:
    """Return one required repository source as an absolute path."""

    return str(ROOT.joinpath(*parts).resolve(strict=True))


from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

sys.path.insert(0, str(SOURCE_ROOT))

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
                        StringStruct("FileDescription", APPLICATION_METADATA.name),
                        StringStruct("FileVersion", f"{APPLICATION_METADATA.version}.0"),
                        StringStruct("InternalName", "Omega"),
                        StringStruct("OriginalFilename", "Omega.exe"),
                        StringStruct("LegalCopyright", APPLICATION_METADATA.copyright),
                        StringStruct("ProductName", APPLICATION_METADATA.name),
                        StringStruct("ProductVersion", APPLICATION_METADATA.version),
                        StringStruct(
                            "Comments",
                            "A safety-first, local-first Windows desktop assistant.",
                        ),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

datas = [
    (source_path("packaging", "defaults", "app_config.yaml"), "config"),
    (source_path("config", "application_aliases.json"), "config"),
    (source_path("config", "command_patterns.json"), "config"),
    (source_path("config", "permissions.json"), "config"),
    (source_path("config", "protected_paths.json"), "config"),
    (source_path("docs", "installation.md"), "docs"),
    (source_path("docs", "security.md"), "docs"),
    (source_path("assets", "videos", "omega_core_loop.mp4"), "assets/videos"),
    (source_path("LICENSE"), "."),
]

hidden_imports = [
    "omega.gui.application",
    "omega.gui_v2.application",
    "omega.gui_v2.video",
    "cv2",
    "PIL.Image",
    "PIL.ImageTk",
    "omega.performance.diagnostics",
    "omega.security.diagnostics",
    "omega.voice.microphone",
    "omega.voice.recognizer",
    "omega.voice.service",
    "omega.voice.speaker",
    "omega.voice.terminal",
]

analysis = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(SOURCE_ROOT)],
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
