# Omega 1.0 manual release checklist

This checklist records human decisions. It does not execute or authorize any action.

## Pre-release

- [ ] Local `main` and `origin/main` are synchronized.
- [ ] Working tree is clean.
- [ ] Application version is `1.0.0` and expected tag is `v1.0.0`.
- [ ] `CHANGELOG.md` and `docs/releases/v1.0.0.md` are final.
- [ ] Black, Ruff, mypy, and the complete pytest suite pass.
- [ ] Security and performance diagnostics pass.
- [ ] Windows portable package builds in a clean environment.
- [ ] Installer builds when applicable and is not silently installed.
- [ ] Package contents and executable smoke checks pass.
- [ ] `SHA256SUMS.txt` and bounded build metadata are generated and verified.
- [ ] Databases, logs, caches, models, screenshots, exports, credentials, and private
  data are absent from artifacts.
- [ ] Documentation links, known limitations, and unsigned-build warnings are reviewed.
- [ ] Required GitHub Actions checks on the final commit pass.

## Release

- [ ] Final reviewed commit is pushed to `main`.
- [ ] Local and remote `main` still identify the intended release commit.
- [ ] Tag `v1.0.0` is created from that exact commit and pushed manually.
- [ ] Tag-triggered release workflow succeeds without permission escalation.
- [ ] Verified portable ZIP and any verified installer are attached.
- [ ] `SHA256SUMS.txt` and `build-metadata.json` are attached.
- [ ] Published release notes match repository behavior and limitations.
- [ ] Release is marked stable rather than prerelease.
- [ ] A download is checksum-verified and smoke-tested without private data.

## Post-release

- [ ] Installer is tested on a clean supported Windows environment.
- [ ] Portable build is tested where provided.
- [ ] Release issues and security reports are monitored.
- [ ] README release link is added only after a real release exists.
- [ ] Next-version planning starts without silently changing the released tag.
- [ ] Published logs and artifacts are rechecked for secrets or private data.
