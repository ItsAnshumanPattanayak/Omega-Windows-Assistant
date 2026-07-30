# Windows packaging and release builds

## Strategy and prerequisites

Omega uses PyInstaller 6.21.0 in one-folder mode. This keeps resource layout visible,
starts more predictably than one-file extraction, and provides both `OmegaCLI.exe`
(console) and `Omega.exe` (windowed). PyInstaller added Python 3.14 support in 6.15;
the pinned 6.21 toolchain supports the current CPython 3.14 environment. Windows
bundles must be built on Windows; PyInstaller is not a cross-compiler.

The branded installer uses Inno Setup 6 with per-user privileges. Its product and
publisher identity is **Omega Windows Assistant**, developed and published by
**Anshuman Pattanayak**. Build dependencies are
separate from runtime dependencies:

```powershell
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements-build.txt
```

Tool installation is an explicit environment-setup step. Build scripts never download
tools. Current pins are PyInstaller 6.21.0 and pyinstaller-hooks-contrib 2026.6.

## Build and verification

```powershell
.\scripts\build_windows_app.ps1 -Python .\.venv\Scripts\python.exe
.\scripts\build_windows_installer.ps1 -Python .\.venv\Scripts\python.exe
```

The first script runs Black, Ruff, mypy, and pytest unless `-SkipChecks` is explicitly
used, cleans only reviewed generated directories, produces `dist\Omega`, records a
bounded build manifest, and runs `scripts\verify_package.ps1`. The verifier uses an
isolated `OMEGA_DATA_DIR`, checks the privacy manifest, exercises `--version`, `--help`,
`--gui-check`, initializes the database, checks executable version metadata, and opens
the exact packaged GUI process for a bounded launch check before closing only that
process. It never installs the application.

The installer script rebuilds and verifies the bundle, then requires a trusted local
`ISCC.exe`. It creates
`dist\installer\Omega-Windows-Assistant-Setup-v2.0.0.exe`, a matching `.sha256` file,
and `installer-manifest.json`. It does not download Inno Setup, silently install the
result, sign it, publish it, or upload it.

The installer defaults to `%LOCALAPPDATA%\Programs\Omega`, creates an **Omega Windows
Assistant** Start Menu shortcut, and offers an unchecked Desktop shortcut. Installed
Apps displays version 2.0.0 and publisher Anshuman Pattanayak. Upgrades retain the
stable application ID. Uninstall removes application files and shortcuts while
preserving `%LOCALAPPDATA%\Omega`.

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
`.ico` asset. A future icon must be an approved, multi-resolution Omega-specific
asset; third-party branding must not be substituted. Builds are not signed, so both
the executable and installer may trigger Windows SmartScreen or Unknown Publisher
warnings. Bypassing Windows security is not recommended. Optional voice, browser automation, screenshots,
and document formats depend on compatible extras being installed in the build
environment. Report packaging regressions with sanitized tool versions, command,
output path, and bounded error text—never a database, configuration secret, or user
document.

## CI artifacts

The Phase 29 Windows workflow builds on `windows-latest` with Python 3.14 and the
pinned build extra. It always runs package verification before creating
`Omega-<version>-windows-x64.zip`. If trusted Inno Setup is already present, it may
also produce `Omega-Windows-Assistant-Setup-v<version>.exe`; tooling is never bootstrapped through a
downloaded script. `build-metadata.json` records only version, commit/tag, UTC build
time, Python/tool versions, and runner architecture. `SHA256SUMS.txt` hashes only final
ZIP/EXE distributables. Validation artifacts are retained for 14 days; release copies
live in GitHub Releases. See [releasing.md](releasing.md).
