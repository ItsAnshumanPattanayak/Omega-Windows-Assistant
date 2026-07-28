from __future__ import annotations

from uuid import uuid4

import pytest

from omega.personalization import (
    FakePreferenceRepository,
    PersonalizationConfiguration,
    PersonalizationDisabledError,
    PreferenceCategory,
    PreferenceResolver,
    PreferenceService,
    PreferenceSource,
    PreferenceValidator,
    ProfileError,
)


def test_service_creates_and_activates_protected_default_profile(
    service: PreferenceService,
) -> None:
    assert service.active_profile.name == "Default"
    assert service.active_profile.is_default
    with pytest.raises(ProfileError, match="default profile"):
        service.delete_profile("Default", confirmed=True)


def test_disabled_service_does_not_create_profile() -> None:
    configuration = PersonalizationConfiguration(enabled=False)
    repository = FakePreferenceRepository()
    service = PreferenceService(
        configuration,
        repository,
        PreferenceValidator(configuration),
        PreferenceResolver(repository),
    )
    assert repository.list_profiles() == ()
    with pytest.raises(PersonalizationDisabledError):
        _ = service.active_profile


def test_persisted_preference_round_trip(service: PreferenceService) -> None:
    result = service.set_preference("response_verbosity", "concise")
    assert result.changed
    resolved = service.resolver.resolve("response_verbosity")
    assert resolved.value == "concise"
    assert resolved.source is PreferenceSource.ACTIVE_PROFILE


def test_session_override_precedes_profile_and_expires(
    service: PreferenceService,
) -> None:
    session_id = uuid4()
    service.set_preference("response_verbosity", "standard")
    service.set_preference(
        "response_verbosity", "detailed", session_id=session_id, temporary=True
    )
    resolved = service.resolver.resolve("response_verbosity", session_id=session_id)
    assert resolved.value == "detailed"
    assert resolved.source is PreferenceSource.SESSION_OVERRIDE
    service.reset_session(session_id)
    assert (
        service.resolver.resolve("response_verbosity", session_id=session_id).value
        == "standard"
    )


@pytest.mark.parametrize(
    ("key", "attempted", "required"),
    [
        ("mandatory_confirmations", False, True),
        ("cloud_sync", True, False),
        ("behavioral_inference", True, False),
        ("usage_statistics", True, False),
        ("workflow_run_confirmation", False, True),
    ],
)
def test_mandatory_safety_values_override_preferences(
    service: PreferenceService, key: str, attempted: object, required: object
) -> None:
    service.set_preference(key, attempted)
    resolved = service.resolver.resolve(key)
    assert resolved.value is required
    assert resolved.source is PreferenceSource.SAFETY_POLICY
    assert resolved.safety_override


def test_reset_category_preserves_other_categories(service: PreferenceService) -> None:
    service.set_preference("speech_enabled", True)
    service.set_preference("response_verbosity", "concise")
    service.reset_category(PreferenceCategory.VOICE)
    keys = {item.key for item in service.list_preferences()}
    assert "speech_enabled" not in keys
    assert "response_verbosity" in keys


def test_reset_all_requires_confirmation_and_preserves_repository(
    service: PreferenceService, repository: FakePreferenceRepository
) -> None:
    service.set_preference("response_verbosity", "concise")
    marker = object()
    repository.unrelated_data = marker  # type: ignore[attr-defined]
    with pytest.raises(ProfileError, match="confirmation"):
        service.reset_all()
    assert service.reset_all(confirmed=True).changed
    assert service.list_preferences() == ()
    assert repository.unrelated_data is marker  # type: ignore[attr-defined]


def test_multiple_profiles_are_disabled_by_default(service: PreferenceService) -> None:
    with pytest.raises(ProfileError, match="disabled"):
        service.create_profile("Work")


def test_multiple_profile_lifecycle_and_bounds() -> None:
    configuration = PersonalizationConfiguration(
        multiple_profiles_enabled=True, maximum_profiles=2
    )
    repository = FakePreferenceRepository()
    resolver = PreferenceResolver(repository)
    service = PreferenceService(
        configuration,
        repository,
        PreferenceValidator(configuration),
        resolver,
    )
    work = service.create_profile("Work")
    with pytest.raises(ProfileError, match="already exists"):
        service.create_profile("work")
    with pytest.raises(ProfileError, match="limit"):
        service.create_profile("Personal")
    assert service.switch_profile("Work") == work
    with pytest.raises(ProfileError, match="confirmation"):
        service.delete_profile("Work")
    service.delete_profile("Work", confirmed=True)
    assert [item.name for item in repository.list_profiles()] == ["Default"]


def test_switching_profile_invalidates_session_preferences() -> None:
    configuration = PersonalizationConfiguration(multiple_profiles_enabled=True)
    repository = FakePreferenceRepository()
    resolver = PreferenceResolver(repository)
    service = PreferenceService(
        configuration,
        repository,
        PreferenceValidator(configuration),
        resolver,
    )
    session_id = uuid4()
    service.set_preference(
        "response_verbosity", "concise", session_id=session_id, temporary=True
    )
    service.create_profile("Work")
    service.switch_profile("Work")
    assert resolver.session_values(session_id) == {}


def test_profile_names_are_bounded() -> None:
    configuration = PersonalizationConfiguration(multiple_profiles_enabled=True)
    repository = FakePreferenceRepository()
    service = PreferenceService(
        configuration,
        repository,
        PreferenceValidator(configuration),
        PreferenceResolver(repository),
    )
    with pytest.raises(ProfileError):
        service.create_profile("bad|name")


def test_history_summary_reveals_categories_not_private_values(
    service: PreferenceService,
) -> None:
    service.set_preference("display_name", "Private Name")
    summary = service.remembered_summary()
    assert "Private Name" not in summary
    assert "general" in summary
