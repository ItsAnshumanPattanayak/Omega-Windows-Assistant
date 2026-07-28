# Localization

Omega localization is offline, deterministic, and data only. English (`en`, `en_US`)
is the complete base and fallback catalog. Hindi (`hi`, `hi_IN`) is a partial preview,
not full product translation. Its descriptor reports coverage and every missing or
safety-critical confirmation message falls back to English.

## Catalog safety

Catalogs use stable dotted message keys and plain text templates with simple named
placeholders. Validation bounds bytes, entries, message length, and aliases; checks
placeholder parity against English; rejects null/control abuse, executable content,
path traversal, unknown APIs, duplicate packs, and non-namespaced plugin keys; and
records a SHA-256 fingerprint. Catalog files do not contain Python, HTML execution,
callbacks, imports, or entry points.

Omega never sends private email, calendar, document, clipboard, screenshot, workflow,
or AI content to a translation provider. External translation and automatic language-
pack downloads are disabled. Optional local-AI translation output is an unverified
draft requiring review and cannot replace critical confirmation text.

## Commands and Unicode

Localized aliases map only to existing `IntentType` values and still use the normal
parser, dispatcher, permission policy, scoped confirmation, and execution gateway.
English aliases remain available. Ambiguous or obfuscated sensitive aliases require
clarification. NFKC normalization supports Hindi, accents, combining text, and emoji
for matching while preserving original user text. Null bytes, bidi overrides, and
unsafe controls are rejected; zero-width characters are removed and flagged.

## Locale formatting

Formatting respects locale, date style, 12/24-hour time, time zone, and unit
preferences. Authoritative datetimes remain timezone-aware and locale-neutral. The
standard-library formatter provides deterministic English/Indian grouping and safe
fallback formatting; it is not a full CLDR implementation. Unsupported locales or
translations fall back safely instead of changing stored values.

Changing a supported catalog updates service-driven terminal strings immediately.
Some existing tkinter strings are migrated gradually and may require restart or remain
English in Phase 25. Developer logs, paths, URLs, addresses, model/plugin IDs, source
code, database identifiers, and stack traces are never translated.
