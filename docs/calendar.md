# Privacy-first calendar assistance

Phase 19 adds a provider-independent calendar domain to Omega. It is disabled
by default. The bundled `FakeCalendarProvider` is deterministic and performs
zero network operations; it exists for tests and explicit local demonstrations.
Omega does not ship a live provider or request/store calendar credentials.

## Supported workflows

- List today, tomorrow, a named weekday, an ISO date, or the next seven days.
- Search bounded event title, description, and location text.
- Open a numbered event from the current session result set.
- Show deterministic agenda summaries and busy intervals.
- Prepare reviewable event proposals with timezone-aware times, attendees,
  reminders, and bounded recurrence models.
- Exact-confirm event creation, update, cancellation, and invitation responses.
- Select recurrence scope explicitly for recurring update or cancellation.

The deterministic grammar rejects an ambiguous clock such as `at 4`. Use
`at 4 pm` or `at 16:00`. Missing required details cause clarification rather
than assumptions. Local wall times are converted to UTC at provider/storage
boundaries. Nonexistent and ambiguous daylight-saving wall times fail closed.

## Safety and privacy

All calendar commands use the normal parser, session, dispatcher, central
safety gateway, and action lifecycle. Terminal, GUI, and offline voice share
the same policies. Creation is proposal-first; no provider mutation occurs
until the exact scoped confirmation phrase is entered. Update, deletion, and
invitation responses also require single-use confirmation, and existing events
are revalidated by ID and revision before execution.

Provider mutation timeouts are recorded as ambiguous and never retried
automatically. Migration 11 stores only opaque account, operation type, target,
status, provider reference, and timestamps. It stores no event content,
attendees, reminders, or credentials. A uniqueness constraint prevents repeated
mutation attempts across restarts.

Event text is inert. Omega does not render calendar HTML, open event links,
execute attachments, persist callbacks, use pickle, evaluate event text,
schedule shell commands, or reuse confirmations. Session selection and
proposals are process-local and cleared at lifecycle boundaries.

## Configuration

The `calendar:` section in `config/app_config.yaml` contains conservative limits
and mandatory mutation confirmations. `enabled` is false by default. Only the
zero-network `fake` provider identifier is accepted in this phase. Live-provider
authentication and adapters are intentionally deferred.

## Command examples

```text
show my events today
what is on my calendar tomorrow
show my calendar this week
find my meeting with Anshuman
am I free tomorrow at 3 PM
schedule event Planning tomorrow at 4 PM for 30 minutes
open event number 1
delete this event
accept this invitation
```

Event creation without a duration and clock values without AM/PM or 24-hour
notation prompt for clarification. Update and delete commands require a current
event selection. The fake provider supports models for reminders and bounded
daily, weekly, and monthly recurrence; recurring mutations require an explicit
scope. Calendar event text is not sent to command history.

## Testing and troubleshooting

Run `python -m pytest tests/calendar -p no:cacheprovider` for the zero-network
calendar suite. If Omega reports that calendar assistance is disabled, leave it
disabled for normal use or explicitly configure the `fake` provider for a local
demonstration. An invalid timezone, working-hour range, content limit, duration,
or disabled confirmation policy prevents startup with a safe configuration
error. Live-provider connection troubleshooting does not apply because no live
adapter is bundled.
