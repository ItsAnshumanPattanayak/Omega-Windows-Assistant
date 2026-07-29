# Releasing Omega

Phase 29 automates verification and GitHub Release publication but never creates a
version, commit, or tag. Releases are unsigned until a separately approved signing
process exists.

## Dry run and package build

Run the `Windows package build` workflow manually. Its only inputs are booleans for
the optional installer and extended verification. The workflow always produces the
portable `Omega-<version>-windows-x64.zip`; it produces
`Omega-Setup-<version>.exe` only when trusted Inno Setup is already available. It also
produces `build-metadata.json` and `SHA256SUMS.txt`. Artifacts expire after 14 days.

No manual input accepts a command, URL, branch, executable path, or package name.

## Release procedure

1. Review `CHANGELOG.md`, limitations, installation notes, and the clean `main`
   commit intended for release.
2. Confirm `python -m omega.distribution.release validate-version
   --repository-root .` passes.
3. Create and push a conservative version tag matching the authoritative project
   version, for example `v1.0.0`. CI does not create this tag.
4. The `Release` workflow verifies the tag format and version, confirms its commit is
   in `origin/main`, reruns quality/tests/security, calls the verified Windows build,
   and checks every SHA-256 digest again.
5. Only then does the publish job create the GitHub Release from the existing tag and
   upload the verified files. A tag containing an approved prerelease suffix is marked
   as a prerelease.

Any failed prerequisite prevents publication. Correct a mistaken release through a
deliberate maintainer review; never retag by force or rewrite `main`.

## Verifying downloads

```powershell
(Get-FileHash -Algorithm SHA256 .\Omega-1.0.0-windows-x64.zip).Hash.ToLowerInvariant()
Get-Content .\SHA256SUMS.txt
```

The matching entry must contain 64 lowercase hexadecimal characters and the exact
filename. Checksums provide integrity, not publisher identity. Omega builds are
currently unsigned; Windows may display an unknown-publisher warning.

## Release notes and upgrades

Move verified `Unreleased` entries in `CHANGELOG.md` into a dated version section
before tagging. GitHub comparison notes supplement that human-maintained record; they
do not replace safety, upgrade, and known-limitation notes. Per-user data under
`%LOCALAPPDATA%\Omega` is preserved across installer upgrades and uninstall. Back up
important local state before upgrading.
