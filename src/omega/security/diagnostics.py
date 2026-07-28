"""Read-only bounded security diagnostics over validated application settings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from omega.security.configuration import SecurityConfiguration
from omega.security.static_analysis import StaticSecurityScanner

if TYPE_CHECKING:
    from omega.config.settings import Settings


class FindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFORMATION = "information"


@dataclass(frozen=True, slots=True)
class SecurityFinding:
    severity: FindingSeverity
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class SecurityReport:
    findings: tuple[SecurityFinding, ...]

    @property
    def passed(self) -> bool:
        return not any(item.severity is FindingSeverity.ERROR for item in self.findings)


class SecurityDiagnostics:
    def __init__(
        self, configuration: SecurityConfiguration, *, repository_root: Path
    ) -> None:
        self.configuration = configuration
        self.repository_root = repository_root.resolve(strict=False)

    def run(self, settings: Settings) -> SecurityReport:
        findings: list[SecurityFinding] = []

        def record(severity: FindingSeverity, code: str, message: str) -> None:
            if len(findings) < self.configuration.maximum_diagnostic_findings:
                findings.append(SecurityFinding(severity, code, message))

        required_false = {
            "safety.allow_arbitrary_shell_commands": settings.safety.get(
                "allow_arbitrary_shell_commands"
            ),
            "workflows.allow_shell_steps": settings.workflows.get("allow_shell_steps"),
            "workflows.allow_code_execution_steps": settings.workflows.get(
                "allow_code_execution_steps"
            ),
            "plugins.allow_remote_plugin_downloads": settings.plugins.get(
                "allow_remote_plugin_downloads"
            ),
            "plugins.automatically_update_plugins": settings.plugins.get(
                "automatically_update_plugins"
            ),
            "local_ai.automatically_download_models": settings.local_ai.get(
                "automatically_download_models"
            ),
            "localization.allow_external_translation_services": (
                settings.localization.get("allow_external_translation_services")
            ),
            "desktop_utilities.allow_background_clipboard_monitoring": (
                settings.desktop_utilities.get("allow_background_clipboard_monitoring")
            ),
            "desktop_utilities.allow_background_screenshot_capture": (
                settings.desktop_utilities.get("allow_background_screenshot_capture")
            ),
            "personalization.collect_usage_statistics": settings.personalization.get(
                "collect_usage_statistics"
            ),
            "personalization.enable_cloud_sync": settings.personalization.get(
                "enable_cloud_sync"
            ),
        }
        for key, value in required_false.items():
            if value is not False:
                record(FindingSeverity.ERROR, "UNSAFE_SETTING", f"{key} must be false.")
        if settings.safety.get("default_decision") != "deny":
            record(
                FindingSeverity.ERROR,
                "UNSAFE_DEFAULT_DECISION",
                "The safety default decision must remain deny.",
            )
        else:
            record(
                FindingSeverity.INFORMATION,
                "DEFAULT_DENY_ACTIVE",
                "Central safety policy defaults to deny.",
            )
        if settings.local_ai.get("allow_remote_endpoints") is not False:
            record(
                FindingSeverity.ERROR,
                "REMOTE_AI_ENDPOINT",
                "Remote local-AI endpoints must remain disabled.",
            )
        if not (self.repository_root / ".gitignore").is_file():
            record(
                FindingSeverity.WARNING,
                "GITIGNORE_MISSING",
                "Repository ignore policy could not be verified.",
            )
        source_root = self.repository_root / "src" / "omega"
        for finding in StaticSecurityScanner().scan(source_root):
            record(
                FindingSeverity.ERROR,
                finding.code,
                f"{finding.path}:{finding.line}: {finding.message}",
            )
        record(
            FindingSeverity.INFORMATION,
            "DIAGNOSTIC_LOCAL_ONLY",
            "Security diagnostics completed locally without modifying state.",
        )
        return SecurityReport(tuple(findings))


def format_security_report(report: SecurityReport) -> str:
    lines = ["Omega security diagnostics"]
    lines.extend(
        f"{item.severity.value.upper()}: {item.code}: {item.message}"
        for item in report.findings
    )
    lines.append("RESULT: PASS" if report.passed else "RESULT: FAIL")
    return "\n".join(lines)
