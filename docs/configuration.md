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
with a safe configuration error. Tracked configuration contains no personal values,
credentials, tokens, model paths, or machine-specific locations.
