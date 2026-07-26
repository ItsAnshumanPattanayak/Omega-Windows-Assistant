# Privacy-first email assistance

Phase 18 introduces Omega's provider-independent email domain. Email is disabled
by default and a live mailbox adapter is not bundled or claimed as verified.
Automated tests use a deterministic in-memory provider that performs zero network
operations.

## Supported workflows

- Show bounded latest or unread message summaries.
- Search by bounded free text, sender, or subject.
- Open a numbered result as sanitized, bounded plain text.
- Produce a deterministic local extractive summary.
- Show attachment filename, MIME type, size, and identifier metadata.
- Create a reviewable new or reply draft and update its subject or body.
- List drafts.
- Send one exact draft only after full review and exact confirmation.
- Archive one exact message only after confirmation.

Example commands include `Show my latest emails`, `Find emails from
sender@example.com`, `Open email number 1`, `Summarize this email`, `Draft an
email to person@example.com subject Project update`, `Show my drafts`, `Send
this draft`, and `Archive this email`.

Selections are process- and session-local. A new list or search invalidates the
previous current-message selection. Timeout, shutdown, and interruption clear
email selections and pending confirmations.

## Configuration and credentials

Tracked `config/app_config.yaml` contains conservative limits only:

```yaml
email:
  enabled: false
  provider: null
  account_name: null
  maximum_messages_per_request: 20
  maximum_search_query_characters: 300
  maximum_body_characters: 20000
  maximum_summary_characters: 1500
  maximum_recipients: 10
  maximum_subject_characters: 300
  maximum_draft_body_characters: 50000
  provider_timeout_seconds: 20
  allow_attachment_downloads: false
  maximum_attachment_bytes: 10485760
  require_confirmation_for_send: true
  require_confirmation_for_archive: true
```

Never put addresses, passwords, app passwords, access or refresh tokens, server
secrets, or machine-specific secret paths in tracked configuration. A future
live adapter must define environment-variable names or OS credential-store
integration and resolve credentials only at explicit startup. No live adapter is
enabled in Phase 18.

For isolated development only, `enabled: true`, `provider: fake`, and a
non-sensitive account profile name select the zero-network fake. The application
fake starts empty; tests inject inert messages.

## Privacy and safety

Message bodies, recipients, subjects, attachment contents, credentials, and raw
provider errors are excluded from normal logs. Email gateway command records are
redacted before persistent history. SQLite migration 10 stores only minimal
send/archive idempotency metadata, never mailbox or draft bodies, credentials,
or attachment binaries.

Omega does not render HTML, load remote images, open links, download or execute
attachments, send attachments, permanently delete mail, perform bulk mutation,
run arbitrary provider commands, or use cloud AI. Attachment filenames reject
path traversal. Recipient and subject newlines are rejected to prevent header
injection.

A draft cannot send itself. The send prompt displays recipients, subject, and
body and requires the exact draft-specific phrase. Confirmations are single-use,
session-scoped, expiring, and replay-protected. An ambiguous provider timeout is
recorded and blocks retries. Archive is separately confirmed; permanent deletion
is absent from the provider protocol.

## Testing and troubleshooting

```powershell
python -m pytest tests/email -v -p no:cacheprovider
```

If Omega says email is disabled, no mailbox operation was attempted. If it says
no provider is configured, configure only an explicitly supported adapter.
Provider failures remain bounded and redact sensitive details. There is no live
provider troubleshooting claim because no live provider was tested.
