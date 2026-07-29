from __future__ import annotations

import re
import subprocess
from pathlib import Path

from omega.config import load_settings
from omega.database.migrations import DEFAULT_MIGRATIONS
from omega.database.schema import LATEST_SCHEMA_VERSION
from omega.distribution.release import project_version, validate_version_sources
from omega.models import IntentType
from omega.understanding.patterns import INTENT_PATTERNS
from omega.utils.constants import APP_VERSION

ROOT = Path(__file__).resolve().parents[2]


def test_authoritative_release_version_is_1_0_0() -> None:
    assert project_version(ROOT) == "1.0.0"
    assert APP_VERSION == "1.0.0"
    assert validate_version_sources(ROOT, tag="v1.0.0") == "1.0.0"
    settings = load_settings(ROOT / "config" / "app_config.yaml")
    assert settings.application_version == "1.0.0"


def test_migration_chain_is_contiguous_unique_and_current() -> None:
    versions = [migration.version for migration in DEFAULT_MIGRATIONS]
    names = [migration.name for migration in DEFAULT_MIGRATIONS]
    assert versions == list(range(1, LATEST_SCHEMA_VERSION + 1))
    assert len(names) == len(set(names))


def test_all_actionable_intents_have_parser_routes() -> None:
    static = {pattern.intent for pattern in INTENT_PATTERNS}
    dynamic = {
        IntentType.OPEN_FILE,
        IntentType.OPEN_FOLDER,
        IntentType.RENAME_FOLDER,
        IntentType.COPY_FOLDER,
        IntentType.MOVE_FOLDER,
        IntentType.DELETE_FOLDER,
        IntentType.CHECK_FOLDER_EXISTENCE,
        IntentType.GET_FOLDER_INFORMATION,
    }
    session_owned = {
        IntentType.ACTIVATE_ASSISTANT,
        IntentType.HELP,
        IntentType.SHUTDOWN_ASSISTANT,
    }
    expected = set(IntentType) - {IntentType.UNKNOWN}
    assert static | dynamic | session_owned == expected


def test_all_executable_intents_have_dispatch_references() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src" / "omega" / "execution").glob("*dispatcher.py")
    )
    names = set(re.findall(r"IntentType\.([A-Z][A-Z0-9_]+)", source))
    session_owned = {"ACTIVATE_ASSISTANT", "HELP", "SHUTDOWN_ASSISTANT"}
    expected = {intent.name for intent in IntentType} - {"UNKNOWN"} - session_owned
    assert expected <= names


def test_all_executable_intents_have_risk_classification() -> None:
    source = (ROOT / "src" / "omega" / "safety" / "classifier.py").read_text(
        encoding="utf-8"
    )
    names = set(re.findall(r"IntentType\.([A-Z][A-Z0-9_]+)", source))
    session_owned = {"ACTIVATE_ASSISTANT", "HELP", "SHUTDOWN_ASSISTANT"}
    expected = {intent.name for intent in IntentType} - session_owned
    assert expected <= names


def test_security_critical_configuration_defaults_are_fail_closed() -> None:
    settings = load_settings(ROOT / "config" / "app_config.yaml")
    configurations = (
        settings.database_configuration,
        settings.voice_configuration,
        settings.browser_configuration,
        settings.system_configuration,
        settings.scheduling_configuration,
        settings.productivity_configuration,
        settings.knowledge_configuration,
        settings.email_configuration,
        settings.calendar_configuration,
        settings.desktop_utilities_configuration,
        settings.workflow_configuration,
        settings.plugin_configuration,
        settings.ai_configuration,
        settings.personalization_configuration,
        settings.accessibility_configuration,
        settings.localization_configuration,
        settings.security_configuration,
        settings.performance_configuration,
    )
    assert all(configuration is not None for configuration in configurations)
    security = settings.security_configuration
    assert security.enabled
    assert not any(
        (
            security.allow_shell_execution,
            security.allow_dynamic_code_execution,
            security.allow_automatic_email_send,
            security.allow_automatic_calendar_mutation,
            security.allow_confirmation_bypass,
            security.allow_remote_plugin_downloads,
            security.allow_automatic_plugin_updates,
            security.allow_automatic_model_downloads,
            security.allow_external_translation_services,
            security.allow_background_clipboard_monitoring,
            security.allow_background_screenshot_capture,
            security.allow_telemetry,
            security.allow_cloud_sync,
        )
    )
    assert settings.safety["default_decision"] == "deny"
    assert settings.files["allow_permanent_deletion"] is False
    assert settings.folders["allow_permanent_deletion"] is False


def test_required_release_documents_and_local_links_exist() -> None:
    required = (
        ROOT / "CHANGELOG.md",
        ROOT / "SECURITY.md",
        ROOT / "docs" / "release_readiness.md",
        ROOT / "docs" / "release_checklist.md",
        ROOT / "docs" / "known_limitations.md",
        ROOT / "docs" / "releases" / "v1.0.0.md",
    )
    assert all(path.is_file() for path in required)
    for document in required:
        content = document.read_text(encoding="utf-8")
        for target in re.findall(
            r"\[[^\]]+\]\((?!https?://|#|mailto:)([^)#]+)", content
        ):
            assert (document.parent / target).resolve().exists(), (document, target)


def test_all_documentation_local_links_resolve() -> None:
    documents = [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "SECURITY.md"]
    documents.extend((ROOT / "docs").rglob("*.md"))
    for document in documents:
        content = document.read_text(encoding="utf-8")
        targets = re.findall(
            r"\[[^\]]+\]\((?!https?://|#|mailto:)([^)#]+)(?:#[^)]+)?\)",
            content,
        )
        for raw_target in targets:
            target = raw_target.strip("<>")
            assert (document.parent / target).resolve().exists(), (document, target)


def test_no_machine_specific_paths_or_private_artifacts_are_tracked() -> None:
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.splitlines()
    prohibited_suffixes = {
        ".db",
        ".sqlite",
        ".sqlite3",
        ".log",
        ".dmp",
        ".gguf",
        ".onnx",
        ".safetensors",
        ".exe",
        ".msi",
    }
    assert not [
        name for name in tracked if Path(name).suffix.casefold() in prohibited_suffixes
    ]
    reviewed_roots = (
        "src/",
        "config/",
        "packaging/",
        "installer/",
        "scripts/",
        ".github/",
    )
    for name in tracked:
        normalized = name.replace("\\", "/")
        if normalized.startswith(reviewed_roots):
            payload = (ROOT / name).read_text(encoding="utf-8", errors="ignore")
            assert re.search(r"(?i)[a-z]:\\users\\[^\\]+", payload) is None


def test_release_script_is_validation_only() -> None:
    script = (ROOT / "scripts" / "verify_release.ps1").read_text(encoding="utf-8")
    prohibited = (
        "git commit",
        "git push",
        "git tag",
        "gh release",
        "git reset",
        "git clean",
        "Remove-Item",
        "Invoke-WebRequest",
        "Start-Process",
    )
    assert all(value.casefold() not in script.casefold() for value in prohibited)
