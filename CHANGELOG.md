# Changelog

Notable changes are recorded here. Entries describe repository behavior and do not
imply that an artifact has already been published.

## Unreleased

### Added

- Read-only pull-request and `main` validation for formatting, linting, typing,
  tests, import safety, security diagnostics, and CLI smoke checks.
- A Windows package workflow with versioned portable artifacts, bounded metadata,
  SHA-256 checksums, package verification, and optional trusted installer builds.
- A tag-only GitHub Release workflow and conservative Dependabot configuration.

### Changed

- Release and packaging procedures now have explicit trust, retention, version, and
  branch-protection documentation.

### Fixed

- None recorded.

### Security

- Ordinary CI remains read-only; release write permission is isolated to the final
  publish job after required validation.
- Release archives reject private runtime data, databases, logs, models, plugin
  storage, private keys, credentials, and traversal entries.

### Deprecated

- None.

### Removed

- None.
