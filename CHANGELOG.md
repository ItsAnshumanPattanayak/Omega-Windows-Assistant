# Changelog

Notable changes are recorded here. Entries describe repository behavior and do not
imply that an artifact has already been published.

## [2.0.0] - Unreleased

### Added

- Context-bound application-name clarifications for registered applications and
  aliases, routed through the existing dispatcher and safety gateway.
- Chat-oriented GUI message layout, collapsible recent activity, and categorized
  More Activities navigation that preserves every Version 1 action.
- Voice readiness diagnostics and explicit configured-microphone validation.

### Changed

- The supported offline English model is now the official 128 MB
  `vosk-model-en-us-0.22-lgraph`; local model files remain ignored by Git.
- Default ordinary-command confidence is `0.60`, while sensitive voice
  confirmations default to `0.90` and cannot be configured below `0.80`.
- Application metadata, packaged defaults, runtime output, and release tooling now
  consistently report Version `2.0.0`.

### Fixed

- The GUI controller continues to be initialized before toolbar construction.

### Security

- Bare yes/no responses authorize only a current, unexpired application
  clarification and never replace exact confirmation for sensitive actions.

### Deprecated

- None.

## [1.0.0] - 2026-07-29

### Added

- Terminal, tkinter GUI, and optional offline voice command lifecycles backed by
  strongly typed commands, actions, errors, and results.
- Deterministic command understanding and centralized safety, permission, protected
  resource, exact-confirmation, replay-prevention, and lifecycle persistence controls.
- Safe application, file, folder, browser, system, recovery, history, scheduling,
  productivity, knowledge, email, calendar, desktop utility, workflow, plugin, local
  AI, personalization, accessibility, and localization boundaries.
- SQLite migrations 1 through 14, fake-provider integration coverage, and bounded
  local import/export formats.
- Windows package and per-user installer sources, private-artifact verification,
  release metadata, and SHA-256 manifests.
- Read-only pull-request and `main` CI, security validation, Windows package builds,
  conservative Dependabot updates, and tag-only GitHub Release automation.
- Final release-readiness matrix, known limitations, release notes, security reporting
  policy, and manual release checklist.

### Changed

- Application, packaged configuration, CLI, installer, artifact, and release-tag
  metadata now consistently target version `1.0.0` and tag `v1.0.0`.
- Documentation now distinguishes source-verified features, optional integrations,
  live-provider/hardware limits, and binary-build verification requirements.

### Fixed

- Phase 29 path-policy tests were made portable for GitHub-hosted Windows runners and
  invalid Windows test-path characters were removed.

### Security

- Destructive or provider-mutating actions remain gateway-controlled and exactly
  confirmed; confirmation receipts cannot authorize a different action.
- Shell/dynamic execution, permanent deletion, automatic provider mutation, telemetry,
  cloud sync, background capture, and remote plugin/model acquisition remain disabled.
- CI is read-only except for the final verified tag-release publication job. Release
  archives reject private runtime data, credentials, databases, logs, models, exports,
  traversal entries, and unexpected metadata.

### Known Limitations

- Windows binaries are unsigned, and a real clean-machine executable/installer build
  remains required before attaching binary artifacts.
- Voice, browser, email/calendar, plugins, and local AI depend on explicit optional
  local setup. See `docs/known_limitations.md` for the complete reviewed list.

### Removed

- None.
