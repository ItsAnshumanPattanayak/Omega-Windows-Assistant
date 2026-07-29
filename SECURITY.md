# Security policy

## Supported release

Security fixes target the latest stable Omega release and current `main`. Older source
snapshots may not receive fixes.

## Private reporting

Use the repository's GitHub **Security** tab to submit a private vulnerability report
when private vulnerability reporting is enabled. If it is unavailable, open a minimal
issue asking maintainers for a private contact channel without including exploit
details, credentials, private files, database copies, or personal paths.

Include the Omega version, affected feature, expected safety boundary, and the
smallest sanitized reproduction. Do not test destructive behavior against real user
data or live provider accounts. Maintainers should acknowledge, triage, remediate,
test, and coordinate disclosure before publishing sensitive details.

See [docs/security.md](docs/security.md) and
[docs/threat_model.md](docs/threat_model.md) for supported boundaries and limitations.
