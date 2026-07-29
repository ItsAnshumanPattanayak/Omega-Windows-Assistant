# Configuration

Phase 25 adds `accessibility` and `localization` sections to
`config/app_config.yaml`. Configuration is validated during explicit application
startup; importing Omega has no catalog, GUI, speech, database, or network side effect.

Font scale defaults to `1.0` within `0.8`–`2.0`. Confirmation timeout multipliers
default to `1.0` and cannot exceed the configured bounded maximum. Keyboard navigation,
keyboard hints, and local English localization are enabled. High contrast, reduced
motion, and screen-reader-friendly modes are explicit opt-ins.

`allow_external_translation_services` and `automatically_download_language_packs`
must remain `false`. Catalogs default to 1 MiB, 10,000 entries, 10,000 characters per
message, and 50 aliases per intent. Unknown settings or unsafe limits prevent startup
with a safe configuration error. The development `config/app_config.yaml` may contain
local display or optional-device/model settings and is never packaged. The
distribution uses the separately reviewed non-personal template documented below;
neither file may contain credentials or tokens.

## Version 2 voice and clarification settings

The source configuration selects the relative local model directory
`vosk-model-en-us-0.22-lgraph`. The non-personal packaged template keeps voice
disabled and its model path unset because Omega never downloads or packages model
data. Existing Version 1 user configuration remains user-owned and missing settings
receive safe defaults.

`voice.microphone_device` accepts `null` for the system default, a non-negative input
index, or an exact input-device name. Use `omega --list-audio-devices` to discover
bounded device metadata. Ordinary and sensitive confidence thresholds default to
`0.60` and `0.90`, and sensitive confirmation cannot be set below `0.80`.

`assistant.application_clarification_timeout_seconds` defaults to 30 seconds. It
controls only the expiring application-name question and does not alter the central
confirmation timeout or policy.
## Phase 26 security configuration

The `security` section defines bounded command, JSON, diagnostic, log, and archive
limits. It is validated as an immutable `SecurityConfiguration`; unknown keys and
out-of-range values fail startup. Mandatory protections—including log redaction and
the prohibition of shell/dynamic execution, confirmation bypass, automatic remote
acquisition, background capture, telemetry, and cloud sync—cannot be disabled by
configuration. See [security.md](security.md).

## Phase 27 performance configuration

The `performance` section bounds timing records, diagnostic runs, and parser/workflow/
plugin caches. Timing collection is disabled by default. Sensitive-content caching
and telemetry are mandatory false; unknown settings or unsafe values fail
configuration loading. See [performance.md](performance.md).

## Packaged configuration

Source execution continues to read `config/app_config.yaml`. Windows bundles contain
the separate, non-personal template `packaging/defaults/app_config.yaml`. On first
packaged startup it is copied to `%LOCALAPPDATA%\Omega\config\app_config.yaml`; later
starts and upgrades preserve that user-owned file. Code defaults supply missing
optional fields, while missing required sections or invalid values produce a bounded
configuration error. The packaged template disables voice, local AI, provider
accounts, user plugins, background capture, sensitive caching, and telemetry.

For isolated package verification only, `OMEGA_DATA_DIR` may select an absolute
temporary runtime root. Relative values are rejected. Secrets and provider tokens do
not belong in the packaged template or installation directory.
