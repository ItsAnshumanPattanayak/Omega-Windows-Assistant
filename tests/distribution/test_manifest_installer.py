from pathlib import Path

import pytest

from omega.core.exceptions import DistributionError
from omega.distribution import require_safe_distribution, verify_distribution


def test_distribution_manifest_accepts_bounded_public_resources(tmp_path: Path) -> None:
    root = tmp_path / "Omega"
    (root / "_internal" / "config").mkdir(parents=True)
    (root / "Omega.exe").write_bytes(b"executable")
    (root / "_internal" / "config" / "permissions.json").write_text(
        "{}", encoding="utf-8"
    )
    result = require_safe_distribution(root)
    assert result.passed and result.files_inspected == 2


@pytest.mark.parametrize(
    "relative",
    [
        ".env",
        "credentials.json",
        "data/omega.db",
        "logs/omega.log",
        "tests/test_private.py",
        "voice_models/model.bin",
        "ai_models/model.gguf",
        "screenshots/private.png",
    ],
)
def test_distribution_manifest_rejects_private_artifacts(
    tmp_path: Path, relative: str
) -> None:
    root = tmp_path / "Omega"
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"private")
    result = verify_distribution(root)
    assert not result.passed
    with pytest.raises(DistributionError, match="Prohibited distribution files"):
        require_safe_distribution(root)


def test_distribution_manifest_rejects_secret_content_without_echoing_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "Omega"
    root.mkdir()
    secret = root / "settings.txt"
    secret.write_text("api_key=super-secret-value", encoding="utf-8")
    with pytest.raises(DistributionError) as raised:
        require_safe_distribution(root)
    assert "super-secret-value" not in str(raised.value)
    assert "settings.txt" in str(raised.value)


def test_pyinstaller_spec_includes_only_reviewed_resource_groups() -> None:
    spec = Path("packaging/omega.spec").read_text(encoding="utf-8")
    for resource in (
        "app_config.yaml",
        "application_aliases.json",
        "command_patterns.json",
        "permissions.json",
        "protected_paths.json",
        "installation.md",
        "security.md",
        "omega_core_loop.mp4",
        "LICENSE",
    ):
        assert resource in spec
    for prohibited in ("data\\", "voice_models", "ai_models", "tests\\"):
        assert prohibited not in spec
    assert 'name="OmegaCLI"' in spec and 'name="Omega"' in spec
    assert "console=True" in spec and "console=False" in spec
    for hidden_import in (
        "omega.gui_v2.application",
        "omega.gui_v2.video",
        "cv2",
        "PIL.Image",
        "PIL.ImageTk",
    ):
        assert hidden_import in spec
    for metadata in (
        "CompanyName",
        "FileDescription",
        "FileVersion",
        "ProductName",
        "ProductVersion",
        "InternalName",
        "OriginalFilename",
        "LegalCopyright",
        "Comments",
    ):
        assert metadata in spec


def test_safe_packaged_default_has_no_personal_or_model_values() -> None:
    content = Path("packaging/defaults/app_config.yaml").read_text(encoding="utf-8")
    assert "Anshuman" not in content
    assert "vosk-model" not in content
    assert "enabled: false" in content
    assert "enable_telemetry: false" in content


def test_installer_is_per_user_explicit_and_preserves_user_data() -> None:
    script = Path("installer/omega.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in script
    assert "{localappdata}\\Programs\\Omega" in script
    assert "Start Menu" not in script or "{group}" in script
    assert "desktopicon" in script and "Flags: unchecked" in script
    assert "postinstall skipifsilent unchecked" in script
    assert "UninstallDelete" not in script
    assert "{localappdata}\\Omega" in script
    assert '#define MyAppName "Omega Windows Assistant"' in script
    assert '#define MyAppPublisher "Anshuman Pattanayak"' in script
    assert "AppVerName={#MyAppName} {#MyAppVersion}" in script
    assert "OutputBaseFilename=Omega-Windows-Assistant-Setup-v{#MyAppVersion}" in script
    assert "OutputDir=..\\dist\\installer" in script
    assert "Launch Omega Windows Assistant by Anshuman Pattanayak" in script
    for prohibited in ("firewall", "scheduledtask", "runascurrentuser"):
        assert prohibited not in script.casefold()


def test_build_scripts_use_safe_roots_and_do_not_download_tools() -> None:
    windows = Path("scripts/build_windows_app.ps1").read_text(encoding="utf-8")
    installer = Path("scripts/build_windows_installer.ps1").read_text(encoding="utf-8")
    verifier = Path("scripts/verify_package.ps1").read_text(encoding="utf-8")
    assert "Remove-KnownGeneratedDirectory" in windows
    assert "git -C $RepositoryRoot rev-parse --show-toplevel" in windows
    assert "no:cacheprovider" in windows
    assert "Omega-build-manifest.json" in windows
    assert "Inno Setup 7\\ISCC.exe" in installer
    assert "Inno Setup 6\\ISCC.exe" in installer
    assert "Get-Command ISCC.exe" in installer
    assert "Inno Setup compiler ISCC.exe was not found" in installer
    assert "Omega-Windows-Assistant-Setup-v$ExpectedVersion.exe" in installer
    assert "Get-FileHash" in installer
    assert "OMEGA_DATA_DIR" in verifier
    combined = (windows + installer + verifier).casefold()
    assert "pip install" not in combined
    assert "invoke-webrequest" not in combined
    assert "git clean" not in combined
    assert "reset --hard" not in combined


def test_distribution_metadata_uses_official_branding() -> None:
    from omega.distribution import APPLICATION_METADATA

    metadata = APPLICATION_METADATA
    assert metadata.name == "Omega Windows Assistant"
    assert metadata.publisher == metadata.developer == "Anshuman Pattanayak"
    assert metadata.version == "2.0.0"
    assert metadata.support_url.endswith("/issues")
    assert metadata.updates_url.endswith("/releases")
    assert metadata.copyright == "Copyright (c) 2026 Anshuman Pattanayak"
