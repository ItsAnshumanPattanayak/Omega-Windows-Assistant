from pathlib import Path

from omega.__main__ import main
from omega.config import load_settings
from omega.security.diagnostics import SecurityDiagnostics
from omega.security.rate_limit import SlidingWindowRateLimiter
from omega.security.static_analysis import StaticSecurityScanner
from omega.utils.paths import project_root


def test_rate_limiter_is_bounded_and_recovers() -> None:
    now = [10.0]
    limiter = SlidingWindowRateLimiter(2, 5.0, clock=lambda: now[0])
    assert limiter.acquire().allowed
    assert limiter.acquire().allowed
    denied = limiter.acquire()
    assert not denied.allowed and denied.retry_after_seconds == 5.0
    now[0] = 15.1
    assert limiter.acquire().allowed


def test_static_scanner_detects_execution_primitives_without_running_them(
    tmp_path: Path,
) -> None:
    source = tmp_path / "unsafe.py"
    source.write_text(
        "import os, subprocess\n"
        "os.system('never-run')\n"
        "subprocess.run(['safe'], shell=True)\n"
        "eval('1 + 1')\n",
        encoding="utf-8",
    )
    findings = StaticSecurityScanner().scan(tmp_path)
    assert {finding.code for finding in findings} == {
        "DYNAMIC_EXECUTION",
        "SHELL_EXECUTION",
    }


def test_repository_security_diagnostic_is_read_only_and_passes() -> None:
    settings = load_settings()
    report = SecurityDiagnostics(
        settings.security_configuration, repository_root=project_root()
    ).run(settings)
    assert report.passed
    assert any(item.code == "DEFAULT_DENY_ACTIVE" for item in report.findings)


def test_security_check_entry_point(capsys: object) -> None:
    assert main(["--security-check"]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "RESULT: PASS" in output
