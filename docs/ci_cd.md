# CI/CD and repository controls

## Workflow map

Omega uses GitHub-hosted Windows runners and requires no production credentials.

| Workflow | Trigger | Authority | Purpose | Retention |
| --- | --- | --- | --- | --- |
| `CI` | pull requests to `main`, pushes to `main`, manual | `contents: read` | formatting, linting, strict typing, full tests, imports, CLI smoke checks | none |
| `Security` | pull requests/pushes to `main`, weekly, manual | `contents: read` | adversarial tests, safety tests, local diagnostics, PR dependency review | none |
| `Windows package build` | `main`, version tags, bounded manual dispatch, reusable call | `contents: read` | verified portable bundle, optional installer, metadata, SHA-256 manifest | 14 days |
| `Release` | an existing `v*` tag only | read by default; `contents: write` only in publish job | validate, build, checksum-check, create GitHub release | GitHub Release |

Concurrency cancels superseded branch and pull-request checks. Tag package runs and
release runs are not cancelled by unrelated work. CI never creates tags, changes
versions, commits generated output, publishes on an ordinary push, or runs on a
self-hosted runner.

## Python and Windows policy

Source compatibility remains Python 3.11 or newer. Quality checks use 3.11, import
and CLI compatibility use 3.11 and 3.14, and the authoritative full suite and Windows
packaging use 3.14. Phase 28's pinned PyInstaller toolchain supports that packaging
version. `windows-latest` is authoritative; Omega does not claim full Linux or macOS
support.

Only pip's download cache is used. Its key is maintained by `setup-python` and includes
the interpreter and `pyproject.toml`; virtual environments, application data,
databases, models, screenshots, and logs are never cached or uploaded.

## Trust and secrets boundaries

Pull-request workflows receive read-only repository permission and reference no
provider credentials. They do not use `pull_request_target`, run plugins, contact
email/calendar accounts, download speech or AI models, or access personal files.
Only the final release-publishing job receives `contents: write`, through GitHub's
short-lived token, after validation and package jobs succeed.

Dependency review may require GitHub's dependency graph or GitHub Code Security,
depending on repository visibility and plan. Dependabot opens bounded monthly pip and
GitHub Actions update pull requests; it never auto-merges them. Human review and the
same required checks remain mandatory.

## Branch protection recommendations

Configure a ruleset for `main` in repository settings:

- require a pull request and an appropriate human review before merging;
- require the `CI` quality, full-suite, compatibility, and project-security checks;
- require the branch to be current before merging;
- prohibit force pushes and branch deletion (that is, allow no force pushes);
- restrict direct pushes where practical;
- require signed commits only if maintainers deliberately configure and understand
  the signing workflow.

Repository settings are not changed by these workflows. Some controls and dependency
review capabilities vary by GitHub plan.

## Failure handling

Open the failed job and use the named step's exact command. Packaging failures report
only bounded filenames/categories. Do not upload databases, `.env` files, full logs,
private exports, profiling dumps, or user content for diagnosis. Reproduce locally
with the commands in `README.md`; never weaken a safety test to clear CI.
