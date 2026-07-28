from __future__ import annotations

import pytest

from omega.personalization import (
    PersonalizationConfiguration,
    PreferenceValidationError,
    PreferenceValidator,
)


def test_conservative_configuration_defaults() -> None:
    value = PersonalizationConfiguration()
    assert value.enabled
    assert not value.multiple_profiles_enabled
    assert not value.collect_usage_statistics
    assert not value.enable_cloud_sync
    assert not value.enable_behavioral_inference
    assert not value.allow_sensitive_preference_storage
    assert not value.persist_session_preferences


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("maximum_profiles", 0),
        ("maximum_profiles", 21),
        ("maximum_export_bytes", 10),
        ("default_response_verbosity", "silent"),
        ("default_time_format", "decimal"),
        ("default_date_format", "secret"),
        ("default_unit_system", "unknown"),
        ("collect_usage_statistics", True),
        ("enable_cloud_sync", True),
        ("enable_behavioral_inference", True),
        ("allow_sensitive_preference_storage", True),
        ("persist_session_preferences", True),
    ],
)
def test_configuration_rejects_unsafe_or_invalid_values(
    name: str, value: object
) -> None:
    with pytest.raises(PreferenceValidationError):
        PersonalizationConfiguration(**{name: value})  # type: ignore[arg-type]


def test_unknown_configuration_key_is_rejected() -> None:
    with pytest.raises(PreferenceValidationError):
        PersonalizationConfiguration.from_mapping({"telemetry": True})


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("display_name", " Anshuman ", "Anshuman"),
        ("language", "en", "en"),
        ("locale", "en-US", "en-US"),
        ("time_zone", "Asia/Kolkata", "Asia/Kolkata"),
        ("date_format", "iso", "iso"),
        ("time_format", "24-hour", "24-hour"),
        ("response_verbosity", "concise", "concise"),
        ("default_browser", "chrome", "chrome"),
        ("default_editor", "visual studio code", "visual studio code"),
        ("workspace_alias", "workspace", "workspace"),
        ("quiet_hours", "22:00-07:00", "22:00-07:00"),
        ("working_hours", "09:00-17:00", "09:00-17:00"),
        ("speech_rate", 160, 160),
        ("speech_volume", 0.5, 0.5),
        ("font_scaling", 1.25, 1.25),
        ("default_event_duration_minutes", 45, 45),
        ("ai_maximum_context_turns", 4, 4),
        ("workflow_timeout_seconds", 120, 120),
    ],
)
def test_valid_preferences_are_normalized(
    key: str, value: object, expected: object
) -> None:
    validator = PreferenceValidator(
        PersonalizationConfiguration(),
        application_aliases=("chrome", "visual studio code"),
    )
    assert validator.require(key, value) == expected


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("unknown", "x"),
        ("language", "english"),
        ("locale", "../../bad"),
        ("time_zone", "Mars/Olympus"),
        ("date_format", "custom python"),
        ("time_format", "25-hour"),
        ("default_browser", "C:\\evil.exe"),
        ("default_editor", "not-registered"),
        ("workspace_alias", "../private"),
        ("workspace_alias", "C:\\Users\\private"),
        ("quiet_hours", "10 PM-7 AM"),
        ("working_hours", "25:00-30:00"),
        ("speech_rate", 1000),
        ("font_scaling", 4.0),
        ("display_name", "bad\nname"),
        ("form_of_address", "powershell -Command whoami"),
        ("form_of_address", "api_key=secret"),
    ],
)
def test_invalid_or_sensitive_preferences_are_rejected(key: str, value: object) -> None:
    validator = PreferenceValidator(
        PersonalizationConfiguration(), application_aliases=("chrome",)
    )
    with pytest.raises(PreferenceValidationError):
        validator.require(key, value)
