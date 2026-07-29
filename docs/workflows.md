# Safe workflows

Omega workflows coordinate an ordered, statically bounded list of allowlisted
steps. They are not shell scripts, Python programs, macro recordings, or arbitrary
automation packages. Workflow definitions contain JSON-compatible data only.

## Lifecycle

Create or import a disabled draft, add explicitly typed steps through an
application-facing editor, validate it, preview every service and side effect,
then confirm saving. Running is a separate confirmed operation. Each sensitive
step still enters its existing domain dispatcher and confirmation flow; workflow
approval cannot authorize email sending, calendar mutation, deletion, clipboard
clearing, screenshot deletion, or other sensitive actions in advance.

Definitions have bounded names, descriptions, step counts, serialized size,
timeouts, retries, delays, variables, outputs, and condition depth. Supported
data is limited to scalars, aware timestamps represented as text, safe resource
identifiers, and bounded scalar lists. References use forms such as
`${input.name}` and `${steps.lookup.output}`. Conditions support only fixed
comparisons—no regular-expression programs, dynamic jumps, loops, recursion,
`eval`, or executable expressions.

Execution is sequential and stop-on-failure by default. Cancellation, timeout,
and safe pause state preserve completed summaries. Omega does not promise an
atomic rollback across files, applications, email, calendars, or other providers;
existing recovery is offered only where the underlying domain supports it.

Only manual, scheduled-time, and bounded recurring triggers are modeled. There
are no filesystem, clipboard, email, calendar, process, keyboard, microphone,
screen-content, webhook, or network-listener triggers. A scheduled run stops or
waits when a step needs confirmation and cannot send email, mutate calendars, or
perform destructive work unattended.

SQLite migration 12 stores deterministic definitions and privacy-minimized run
summaries. It omits credentials, tokens, email and calendar bodies, clipboard
contents, screenshot pixels, provider responses, and secret runtime inputs.
JSON imports are size- and schema-checked, reject unknown executable step types,
remain disabled until review, and never execute during import. Exports redact
sensitive argument names.

Commands include `list my workflows`, `show workflow Morning Setup`, `preview
workflow Morning Setup`, `validate workflow Morning Setup`, and `run Morning
Setup`. The GUI exposes workflow listing, draft creation, and preview through the
existing non-blocking controller. Optional providers may cause their associated
step to fail safely without affecting workflow inspection.
## Phase 26 import boundary

Workflow JSON import now rejects duplicate keys, non-finite values, excessive bytes,
nesting, and item counts before the existing allowlisted step/schema validation.
Imported text and variables remain data and cannot create shell or dynamic-code
steps. See [security.md](security.md).

## Phase 27 plan reuse

Planning may reuse an inert plan only for the exact immutable workflow object, within
a bounded process-local LRU. A changed or reloaded definition is a different object
and is fully revalidated. Confirmations, permissions, selected resources, and
execution results are never cached.
