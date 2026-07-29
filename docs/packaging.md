# Windows packaging and release builds

## Strategy and prerequisites

Omega uses PyInstaller 6.21.0 in one-folder mode. This keeps resource layout visible,
starts more predictably than one-file extraction, and provides both `OmegaCLI.exe`
(console) and `Omega.exe` (windowed). PyInstaller added Python 3.14 support in 6.15;
the pinned 6.21 toolchain supports the current CPython 3.14 environment. Windows
bundles must be built on Windows; PyInstaller is not a cross-compiler.

The installer uses Inno Setup 6 with per-user privileges. Build dependencies are
separate from runtime dependencies:

```powershell
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements-build.txt
```

Tool installation is an explicit environment-setup step. Build scripts never download
tools. Current pins are PyInstaller 6.21.0 and pyinstaller-hooks-contrib 2026.6.

## Build and verification

```powershell
.\scripts\build_windows.ps1 -Python .\.venv\Scripts\python.exe
.\scripts\build_installer.ps1 -Python .\.venv\Scripts\python.exe
```

The first script runs Black, Ruff, mypy, and pytest unless `-SkipChecks` is explicitly
used, cleans only `build\pyinstaller` and `dist\Omega`, produces `dist\Omega`, and runs
`scripts\verify_package.ps1`. The verifier uses an isolated `OMEGA_DATA_DIR`, checks
the manifest, exercises `--version`, `--help`, `--gui-check`, initializes the database,
and never installs the application.

The installer script requires an existing verified bundle and `ISCC.exe`. Output is
written to `installer\output`. It does not silently install the result.

## Included resources

The bundle includes the safe packaged YAML template, application aliases, command
patterns, permission rules, protected-path rules, installation/security help, and the
MIT license. Localization catalogs are code-owned validated data. Optional voice
adapters may be collected when their extras are installed, but voice and AI model
directories are never collected.

Tests, Git metadata, virtual environments, caches, development databases, logs,
screenshots, clipboard state, provider sessions, credentials, user plugins, private
documents, exports, and model files are excluded. The manifest scanner reports unsafe
path names only and never echoes detected secret content.

## Reproducibility and limitations

The build version comes from Omega metadata; the installer receives it from the build
script. The spec computes paths relative to its own repository location and does not
embed a username or checkout path intentionally. PyInstaller binaries can still
contain toolchain timestamps or platform-specific loader metadata, so byte-for-byte
reproducibility is not claimed.

No application icon is configured because the repository contains no approved Omega
`.ico` asset. Builds are not signed. Optional voice, browser automation, screenshots,
and document formats depend on compatible extras being installed in the build
environment. Report packaging regressions with sanitized tool versions, command,
output path, and bounded error text—never a database, configuration secret, or user
document.
