# Plugin development

Phase 22 manifest schema version is `1`; Omega plugin API version is `1.0.0`.
A package is a bounded ZIP with `plugin.json` at its root and a relative entry point
such as `plugin:create_plugin`. Versions use `major.minor.patch`.

The manifest declares one known category, capabilities, requested permissions,
supported operating systems, Python compatibility, and extension points. Unknown
critical fields, duplicate declarations, executable paths, control characters, and
unsupported permissions are rejected. The factory receives only `PluginContext`:
plugin ID, API version, approved permissions, and its own bounded configuration. It
does not receive Omega's container, database, credentials, environment, confirmation
internals, or provider clients.

Commands and workflow steps are namespaced as `plugin.<plugin_id>.<name>` and cannot
shadow built-in or protected commands. Test with fakes and temporary approved
directories without network, providers, shell, desktop resources, credentials, pip,
or installation hooks. Same-process plugins are reviewed trusted code, not a secure
process sandbox.
