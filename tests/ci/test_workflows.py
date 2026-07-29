from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _texts() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.yml")
    }


def test_workflow_yaml_parses_and_names_are_unique() -> None:
    texts = _texts()
    assert set(texts) == {"ci.yml", "release.yml", "security.yml", "windows-build.yml"}
    for text in texts.values():
        assert yaml.compose(text) is not None
    matches = [
        re.search(r"^name: (.+)$", text, re.MULTILINE) for text in texts.values()
    ]
    assert all(match is not None for match in matches)
    names = [match.group(1) for match in matches if match is not None]
    assert len(names) == len(set(names))


def test_ci_has_bounded_triggers_permissions_concurrency_and_versions() -> None:
    text = _texts()["ci.yml"]
    assert "pull_request:\n    branches: [main]" in text
    assert "push:\n    branches: [main]" in text
    assert "permissions:\n  contents: read" in text
    assert "cancel-in-progress: true" in text
    assert "runs-on: windows-latest" in text
    assert 'python-version: ["3.11", "3.14"]' in text
    assert "python -m pytest -p no:cacheprovider" in text
    assert "python -m mypy src" in text


def test_release_is_tag_only_and_write_access_is_job_scoped() -> None:
    text = _texts()["release.yml"]
    assert 'tags: ["v*"]' in text
    assert "branches:" not in text
    assert text.count("contents: write") == 1
    assert "publish:\n" in text
    assert text.index("publish:\n") < text.index("contents: write")
    assert "git merge-base --is-ancestor" in text
    assert "validate-version" in text
    assert "Verify checksums before publication" in text
    assert "needs: [validate, build]" in text
    assert "cancel-in-progress: false" in text


def test_windows_build_verifies_before_bounded_upload() -> None:
    text = _texts()["windows-build.yml"]
    assert "runs-on: windows-latest" in text
    assert 'python-version: "3.14"' in text
    assert "./scripts/build_windows.ps1 -Python python -SkipChecks" in text
    assert "verify-artifacts" in text
    assert text.index("verify-artifacts") < text.index("actions/upload-artifact@v4")
    assert "retention-days: 14" in text
    assert "Omega-$Version-windows-x64.zip" in text
    assert "Get-Command iscc.exe" in text
    assert "Invoke-WebRequest" not in text


def test_security_workflow_is_read_only_and_dependency_review_is_pr_only() -> None:
    text = _texts()["security.yml"]
    assert "permissions:\n  contents: read" in text
    assert "github.event_name == 'pull_request'" in text
    assert "actions/dependency-review-action@v4" in text
    assert "tests/security tests/safety" in text


def test_workflows_contain_no_dangerous_or_private_integration_paths() -> None:
    joined = "\n".join(_texts().values()).casefold()
    prohibited = (
        "pull_request_target",
        "self-hosted",
        "git reset --hard",
        "push --force",
        "curl ",
        "invoke-webrequest",
        "email_password",
        "calendar_token",
        "openai_api_key",
        "vosk model",
        "download model",
        "pytest --basetemp",
    )
    assert all(value not in joined for value in prohibited)


def test_dependency_cache_and_dependabot_are_bounded() -> None:
    joined = "\n".join(_texts().values())
    assert "cache-dependency-path: pyproject.toml" in joined
    assert "cache: pip" in joined
    assert ".venv" not in joined
    dependabot = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert yaml.compose(dependabot) is not None
    assert "package-ecosystem: pip" in dependabot
    assert "package-ecosystem: github-actions" in dependabot
    assert dependabot.count("interval: monthly") == 2
    assert "auto" not in dependabot.casefold()


def test_release_and_branch_protection_documentation_exists() -> None:
    ci_cd = (ROOT / "docs" / "ci_cd.md").read_text(encoding="utf-8")
    releasing = (ROOT / "docs" / "releasing.md").read_text(encoding="utf-8")
    assert "Branch protection" in ci_cd
    assert "no force pushes" in ci_cd.casefold()
    assert "v1.0.0" in releasing
    assert "SHA256SUMS.txt" in releasing
