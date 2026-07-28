from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from omega.personalization import (
    FakePreferenceRepository,
    PersonalizationConfiguration,
    PersonalizationContext,
    PreferenceCategory,
    PreferenceResolver,
    PreferenceService,
    PreferenceValidator,
    ProfileExportService,
    ProfileImportService,
)


def test_safe_temporary_profile_phase_24_smoke() -> None:
    configuration = PersonalizationConfiguration(
        multiple_profiles_enabled=True, maximum_profiles=3
    )
    repository = FakePreferenceRepository()
    resolver = PreferenceResolver(repository)
    service = PreferenceService(
        configuration,
        repository,
        PreferenceValidator(
            configuration,
            application_aliases=("chrome", "visual studio code"),
        ),
        resolver,
    )
    side_effects = {
        "network": 0,
        "cloud": 0,
        "provider": 0,
        "shell": 0,
        "email": 0,
        "calendar": 0,
        "file": 0,
        "screenshot": 0,
        "clipboard": 0,
        "ai": 0,
    }
    profile = service.create_profile("Temporary")
    service.switch_profile(profile.name)
    for key, value in (
        ("display_name", "Anshuman"),
        ("response_verbosity", "standard"),
        ("time_zone", "Asia/Kolkata"),
        ("date_format", "iso"),
        ("time_format", "24-hour"),
        ("default_browser", "chrome"),
        ("default_editor", "visual studio code"),
        ("quiet_hours", "22:00-07:00"),
        ("working_hours", "09:00-17:00"),
        ("speech_rate", 160),
        ("font_scaling", 1.25),
    ):
        service.set_preference(key, value)
    session_id = uuid4()
    service.set_preference(
        "response_verbosity", "concise", session_id=session_id, temporary=True
    )
    assert (
        resolver.resolve("response_verbosity", session_id=session_id).value == "concise"
    )
    service.reset_session(session_id)
    assert (
        resolver.resolve("response_verbosity", session_id=session_id).value
        == "standard"
    )
    exporter = ProfileExportService(service, configuration)
    exported = exporter.export_json()
    assert "password" not in exported.casefold()
    importer = ProfileImportService(service, configuration)
    preview = importer.preview(exported)
    assert importer.apply(preview.preview_id, confirmed=True) == 11
    service.reset_category(PreferenceCategory.VOICE)
    service.reset_all(confirmed=True)
    assert service.list_preferences() == ()
    assert repository.get_profile(profile.profile_id) is not None
    assert not any(side_effects.values())


def test_no_telemetry_cloud_or_behavioral_inference_symbols() -> None:
    root = Path(__file__).parents[2] / "src" / "omega" / "personalization"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert "requests." not in source
    assert "subprocess." not in source
    assert "os.system" not in source
    assert "pickle." not in source
    assert "enable_cloud_sync: bool = False" in source
    assert "enable_behavioral_inference: bool = False" in source


def test_export_has_no_unrelated_private_payload(service: PreferenceService) -> None:
    exported = ProfileExportService(
        service, PersonalizationConfiguration()
    ).export_json()
    payload = json.loads(exported)
    assert set(payload) == {"schema_version", "profile", "preferences", "privacy"}


def test_gui_controller_exposes_personalization_commands() -> None:
    from omega.gui.controller import GuiController

    assert callable(GuiController.show_profile)
    assert callable(GuiController.show_preferences)
    assert callable(GuiController.show_privacy_preferences)
    assert callable(GuiController.export_profile)
    assert callable(GuiController.reset_session_preferences)


def test_personalized_formatting_never_changes_safety_output(
    service: PreferenceService,
) -> None:
    service.set_preference("response_verbosity", "concise")
    critical = "Confirmation required.\nType the exact phrase to continue."
    assert (
        PersonalizationContext(service.resolver).format_response(
            critical, safety_critical=True
        )
        == critical
    )
