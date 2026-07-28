"""User-controlled profile and preference orchestration."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from uuid import UUID

from omega.models._serialization import utc_now
from omega.personalization.configuration import PersonalizationConfiguration
from omega.personalization.definitions import DEFINITION_MAP
from omega.personalization.exceptions import PersonalizationDisabledError, ProfileError
from omega.personalization.models import (
    PreferenceCategory,
    PreferenceChangeResult,
    PreferenceScope,
    PreferenceSource,
    UserPreference,
    UserProfile,
)
from omega.personalization.repository import PreferenceRepository
from omega.personalization.resolver import PreferenceResolver
from omega.personalization.validation import PreferenceValidator

_PROFILE_NAME = re.compile(r"^[^\x00-\x1f\x7f<>:;|`]{1,120}$")


class PreferenceService:
    def __init__(
        self,
        configuration: PersonalizationConfiguration,
        repository: PreferenceRepository,
        validator: PreferenceValidator,
        resolver: PreferenceResolver,
        *,
        clock: Callable[[], object] = utc_now,
    ) -> None:
        self.configuration = configuration
        self.repository = repository
        self.validator = validator
        self.resolver = resolver
        self.clock = clock
        self._ensure_default_profile()

    @property
    def active_profile(self) -> UserProfile:
        self._enabled()
        profile_id = self.repository.active_profile_id()
        profile = (
            None if profile_id is None else self.repository.get_profile(profile_id)
        )
        if profile is None:
            raise ProfileError("The active profile is unavailable.")
        return profile

    def create_profile(self, name: str) -> UserProfile:
        self._enabled()
        if (
            not self.configuration.multiple_profiles_enabled
            and self.repository.list_profiles()
        ):
            raise ProfileError("Multiple profiles are disabled.")
        normalized = self._profile_name(name)
        profiles = self.repository.list_profiles()
        if any(item.name.casefold() == normalized.casefold() for item in profiles):
            raise ProfileError("A profile with that name already exists.")
        if len(profiles) >= self.configuration.maximum_profiles:
            raise ProfileError("The profile limit has been reached.")
        profile = UserProfile(normalized)
        self.repository.save_profile(profile)
        return profile

    def switch_profile(self, name: str) -> UserProfile:
        self._enabled()
        profile = self._by_name(name)
        self.repository.set_active_profile(profile.profile_id)
        self.resolver.clear_all_sessions()
        return profile

    def delete_profile(self, name: str, *, confirmed: bool = False) -> None:
        profile = self._by_name(name)
        if profile.is_default:
            raise ProfileError("The default profile cannot be deleted.")
        if self.configuration.require_confirmation_for_profile_delete and not confirmed:
            raise ProfileError("Profile deletion requires confirmation.")
        self.repository.delete_profile(profile.profile_id)

    def set_preference(
        self,
        key: str,
        value: object,
        *,
        session_id: UUID | None = None,
        temporary: bool = False,
    ) -> PreferenceChangeResult:
        self._enabled()
        normalized = self.validator.require(key, value)
        definition = DEFINITION_MAP[key]
        if temporary:
            if session_id is None:
                raise ProfileError("A session preference requires an active session.")
            self.resolver.set_session(session_id, key, normalized)
            return PreferenceChangeResult(
                True,
                "The temporary session preference was applied.",
                key,
                definition.category,
            )
        profile = self.active_profile
        self.repository.set_preference(
            UserPreference(
                profile.profile_id,
                key,
                normalized,
                definition.category,
                PreferenceScope.PROFILE,
                PreferenceSource.LOCAL_PERSISTED,
            )
        )
        self.repository.save_profile(replace(profile, updated_at=utc_now()))
        return PreferenceChangeResult(
            True, "The local preference was saved.", key, definition.category
        )

    def reset_session(self, session_id: UUID) -> PreferenceChangeResult:
        self.resolver.clear_session(session_id)
        return PreferenceChangeResult(True, "Session preferences were reset.")

    def reset_category(self, category: PreferenceCategory) -> PreferenceChangeResult:
        self.repository.delete_preferences(self.active_profile.profile_id, category)
        return PreferenceChangeResult(
            True,
            f"{category.value.replace('_', ' ').title()} preferences were reset.",
            category=category,
        )

    def reset_all(self, *, confirmed: bool = False) -> PreferenceChangeResult:
        if self.configuration.require_confirmation_for_profile_reset and not confirmed:
            raise ProfileError("Resetting all preferences requires confirmation.")
        self.repository.delete_preferences(self.active_profile.profile_id)
        return PreferenceChangeResult(
            True,
            "All optional preferences were reset. Other Omega data was not changed.",
        )

    def list_preferences(self) -> tuple[UserPreference, ...]:
        return self.repository.list_preferences(self.active_profile.profile_id)

    def remembered_summary(self) -> str:
        preferences = self.list_preferences()
        categories = sorted({item.category.value for item in preferences})
        category_text = ", ".join(categories) if categories else "none"
        return (
            f"Omega stores {len(preferences)} explicit preference(s) "
            f"in categories: {category_text}."
        )

    def _ensure_default_profile(self) -> None:
        if not self.configuration.enabled:
            return
        profiles = self.repository.list_profiles()
        if not profiles:
            profile = UserProfile("Default", is_default=True)
            self.repository.save_profile(profile)
            self.repository.set_active_profile(profile.profile_id)
        elif self.repository.active_profile_id() is None:
            self.repository.set_active_profile(profiles[0].profile_id)

    def _enabled(self) -> None:
        if not self.configuration.enabled:
            raise PersonalizationDisabledError("Personalization is disabled.")

    def _profile_name(self, name: str) -> str:
        value = name.strip()
        too_long = len(value) > self.configuration.maximum_profile_name_characters
        if too_long or not _PROFILE_NAME.fullmatch(value):
            raise ProfileError("The profile name is invalid.")
        return value

    def _by_name(self, name: str) -> UserProfile:
        normalized = name.strip().casefold()
        for profile in self.repository.list_profiles():
            if profile.name.casefold() == normalized:
                return profile
        raise ProfileError("The profile was not found.")
