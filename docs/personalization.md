# Privacy-first personalization

Phase 24 lets Omega remember only preferences that the user explicitly sets. Values
remain local in SQLite migration 14, can be inspected and exported, and can be reset
without deleting notes, tasks, knowledge, email/calendar receipts, workflows,
plugins, screenshots, or command history.

## Profiles and precedence

Omega creates one protected `Default` profile. Multiple profiles are disabled by
default; the repository and service support an explicit bounded multi-profile mode
without identity inference or automatic switching.

Resolution is deterministic:

1. mandatory safety policy;
2. session-only override;
3. active profile value;
4. local persisted value;
5. application configuration;
6. built-in default.

Diagnostics report the source tier, not a private value. Mandatory confirmations,
cloud-sync prohibition, behavioral-inference prohibition, telemetry prohibition,
and sensitive workflow confirmation cannot be overridden.

## Available preferences

Allowlisted definitions cover display and greeting settings, verbosity, language,
locale, timezone and date/time format, units, registered application aliases,
approved folder aliases, voice, GUI, notifications, quiet and working hours,
accessibility, email drafting, calendar defaults, local AI behavior, workflows, and
privacy retention. Values are bounded and checked for control characters,
credentials, executable content, unknown enums, invalid time zones, unregistered
applications, unsafe paths, and out-of-range numbers.

Quiet hours never suppress confirmations, safety/security warnings, failures for
active actions, or explicit output. Working hours provide defaults and suggestions
only; Omega never reschedules events or workflows automatically.

## Session-only and persisted changes

`Be concise for this session` creates a process-local override that expires at
session shutdown. `Reset session preferences` removes these overrides. Commands such
as `Call me Anshuman`, `Use 24-hour time`, and `Set my preferred browser to Chrome`
persist only after explicit user wording. Applications must be registered and
folders must use approved aliases.

Broad reset, profile deletion, and import use the existing scoped confirmation
gateway. Reset preserves mandatory defaults and never touches unrelated domain data.

## Export and import

Exports are bounded schema-versioned JSON containing profile metadata and allowlisted
preference values. Credentials, tokens, private bodies, clipboard/screenshot data,
document content, AI prompts/responses, and secret paths are excluded.

Import accepts JSON only. It enforces a byte limit, exact schema, known fields,
per-value validation, a preview, and confirmation. Import cannot execute commands or
activate settings before approval. Pickle, executable YAML, Python, and shell formats
are unsupported.

## Integrations and privacy

- Workflows can resolve only definitions explicitly marked workflow-accessible, and
  application/folder values are revalidated.
- Plugins require version- and fingerprint-bound permissions and can read only
  specifically approved non-sensitive definitions or write their own namespace.
- Local AI receives one requested preference at a time, never the full profile.
- GUI actions use the normal controller and session command path.
- Voice uses ordinary confidence and confirmation policies; low-confidence input
  cannot reach broad reset/import/delete operations.

Omega performs no telemetry, cloud synchronization, advertising profiling,
behavioral inference, sensitive-trait inference, or automatic data collection.
Preference values are omitted from ordinary gateway history and logs.

## Testing and troubleshooting

Run `python -m pytest -p no:cacheprovider tests/personalization` for the focused
suite. Rejected values must be corrected to an allowlisted enum, registered
application alias, approved folder alias, valid IANA timezone, or 24-hour range such
as `22:00-07:00`. Personalization can be disabled conservatively while other Omega
domains continue to function.
