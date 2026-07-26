# Secure plugins

Omega Phase 22 supports explicitly selected, reviewed local Python plugins through a
small versioned API. Discovery reads bounded `plugin.json` files only and never
imports code. Installation accepts local ZIP packages, rejects traversal, symlinks,
native executables, install hooks, and credential-like files, and leaves every new
plugin disabled.

## Trust model

Built-in extensions are repository-reviewed. Locally installed plugins must be
validated, fingerprinted, permissioned, enabled, and loaded from Omega's approved
plugin directory. Invalid, incompatible, changed, or unapproved plugins are not
loaded. Same-process Python is trusted code after approval; permissions reduce
accidental misuse but are not a perfect sandbox. Never install untrusted code.

## Permissions and lifecycle

Approvals are tied to plugin ID, semantic version, and SHA-256 source fingerprint.
Changing source or requested permissions requires review. Available permissions are
bounded to registration and existing Omega service facades; shell execution,
credentials, raw databases, arbitrary network access, hidden capture, automatic
email sending, calendar mutation, and safety bypass are unavailable.

Lifecycle states cover discovery, incompatibility, disabled and permission-pending
review, enabled loading, active operation, failure, quarantine, update review, and
removal. Discovery and validation run no plugin hooks. Activation is lazy and plugin
exceptions are converted to bounded failures. Shutdown is time-bounded where
practical; Python threads cannot be forcibly sandboxed in-process.

Commands include `list plugins`, `show plugin example.readonly`, package validation
and installation, enable/disable, permission review, grant/revoke, reload, and
removal. Installation, enablement, grants, and removal require exact confirmation.

Omega never downloads, automatically updates, invokes pip, runs `setup.py`, or scans
arbitrary directories. Plugin-local JSON storage is isolated and quota-bound.
