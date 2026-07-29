# Installing Omega

## Development installation

Omega supports Python 3.11 or newer for source execution. From a clean checkout:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m omega --version
python -m omega --gui-check
```

The tracked `config/app_config.yaml` is development configuration and is not copied
into a Windows distribution.

## Installed application

Phase 28 defines a per-user Inno Setup installer. It installs application files under
`%LOCALAPPDATA%\Programs\Omega`, creates Start Menu entries for the GUI and CLI, and
offers an unchecked desktop shortcut. It does not install a service, driver, browser
extension, certificate, firewall rule, scheduled task, or automatic startup entry.

The main shortcut starts `Omega.exe --gui`. `OmegaCLI.exe` supports:

```text
--help --version --gui --voice --list-audio-devices --gui-check
--security-check --performance-check
```

## Runtime data and first run

Writable state is stored below `%LOCALAPPDATA%\Omega`:

```text
config\app_config.yaml
database\omega.db
logs\
screenshots\
plugins\
knowledge\
productivity\
temporary\
```

First startup creates managed directories, copies a safe configuration template, and
runs existing SQLite migrations. It does not download models, request provider
credentials, enable plugins, enable telemetry, or capture clipboard/screen content.

Voice remains disabled until explicitly configured with locally installed optional
dependencies and a user-supplied Vosk model. Local AI remains disabled and no model is
bundled or downloaded. Email and calendar providers remain unconfigured. User plugins
are not bundled and remain disabled by default.

## Upgrades and uninstall

Installing a newer build with the same application ID replaces application binaries
and shortcuts. User configuration and `%LOCALAPPDATA%\Omega` remain separate and are
preserved. Missing optional configuration fields receive current safe code defaults;
existing values are not overwritten. Database migrations run on application startup
and do not downgrade a newer schema.

Uninstall removes installed application files and shortcuts but preserves user data by
default. Phase 28 intentionally provides no automatic “remove user data” action. To
remove that data, first back up anything needed, uninstall Omega, and manually review
the exact `%LOCALAPPDATA%\Omega` directory before deleting it.

## Troubleshooting

Logs are rotated under `%LOCALAPPDATA%\Omega\logs`; they are redacted and never written
beside the executable. Run `OmegaCLI.exe --security-check` and
`OmegaCLI.exe --performance-check` for bounded local diagnostics. A missing Vosk model,
local-AI runtime, provider account, or optional plugin is not an installation failure.

Phase 28 builds are unsigned. Windows may display an unknown-publisher warning, and no
claim is made about antivirus certification, Microsoft certification, or universal
Windows compatibility.
