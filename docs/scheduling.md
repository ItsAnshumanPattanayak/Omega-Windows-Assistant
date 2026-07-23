# Local scheduling

Phase 15 adds an explicitly started local scheduler over migration 6.
`scheduled_items` stores UTC due times, bounded inert text, recurrence, timer
state, lifecycle timestamps, and optimistic revisions. `schedule_deliveries`
stores a unique claim per schedule and occurrence. Claim and schedule
finalization happen in one transaction, so recurring items finalize the exact
claimed occurrence rather than their newly calculated due time.

Reminders and alarms accept relative durations or explicit AM/PM times.
Countdown timers accept positive bounded durations and support pause, resume,
cancel, listing, and one completion notification. Reminders and alarms support
showing, rescheduling, cancelling, snoozing, and completion or dismissal.
Recurrence supports bounded daily, weekly, monthly, selected-weekday, and
minute/hour interval rules. Only the next occurrence is stored.

The scheduler starts only when terminal, GUI, or voice mode explicitly runs,
uses one daemon worker and bounded batches, and stops with the application.
Slightly overdue items are delivered once after restart. Older occurrences are
marked missed; recurring items advance directly to their next future
occurrence instead of replaying a backlog. An abandoned claim is marked missed
after the configured timeout and is never notified again. Notification failure
is recorded once and is not retried.

All persisted timestamps are timezone-aware UTC. IANA zones are validated with
`zoneinfo` and the cross-platform `tzdata` database; `system` uses the host
timezone. Local input is converted to UTC, nonexistent or ambiguous DST wall
times are rejected, and calendar recurrence preserves local wall time while
skipping DST gaps/folds. Existing UTC timestamps are never reinterpreted after
a timezone change.

Text, GUI, and voice share `CommandParser`, `OmegaSession`, and
`SafeExecutionGateway`. Terminal and GUI presentation drain a bounded,
thread-safe notification queue. Optional speech uses only an explicitly
initialized local voice speaker and cannot retry delivery. Scheduled command
execution is disabled. No callable, pickle, shell, code, destructive action,
credential operation, or old confirmation is stored or replayed.

Examples include:

- `Remind me tomorrow at 7 PM`
- `Remind me every Monday at 10 AM`
- `Set an alarm every weekday at 7 AM`
- `Start a cooking timer for 20 minutes`
- `Pause the cooking timer`
- `Resume the cooking timer`
- `Snooze the alarm for 10 minutes`
- `List reminders`, `List alarms`, and `List timers`
- `Cancel the reminder` or `Dismiss the alarm`

When more than one active item of a requested type exists, Omega requires its
exact title instead of guessing.

Omega is not a Windows service and cannot notify while it or the computer is
off. There is no cloud, email, mobile, calendar, cron, or Task Scheduler
integration.
