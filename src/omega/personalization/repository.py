"""SQLite and deterministic in-memory preference repositories."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol

from omega.database.connection import DatabaseConnectionFactory
from omega.models._serialization import utc_now
from omega.personalization.models import PreferenceCategory, UserPreference, UserProfile


class PreferenceRepository(Protocol):
    def save_profile(self, profile: UserProfile) -> None: ...
    def list_profiles(self) -> tuple[UserProfile, ...]: ...
    def get_profile(self, profile_id: str) -> UserProfile | None: ...
    def delete_profile(self, profile_id: str) -> None: ...
    def set_active_profile(self, profile_id: str) -> None: ...
    def active_profile_id(self) -> str | None: ...
    def set_preference(self, preference: UserPreference) -> None: ...
    def list_preferences(self, profile_id: str) -> tuple[UserPreference, ...]: ...
    def delete_preferences(
        self, profile_id: str, category: PreferenceCategory | None = None
    ) -> None: ...


class FakePreferenceRepository:
    def __init__(self) -> None:
        self.profiles: dict[str, UserProfile] = {}
        self.preferences: dict[tuple[str, str], UserPreference] = {}
        self.active: str | None = None

    def save_profile(self, profile: UserProfile) -> None:
        self.profiles[profile.profile_id] = profile

    def list_profiles(self) -> tuple[UserProfile, ...]:
        return tuple(
            sorted(self.profiles.values(), key=lambda item: item.name.casefold())
        )

    def get_profile(self, profile_id: str) -> UserProfile | None:
        return self.profiles.get(profile_id)

    def delete_profile(self, profile_id: str) -> None:
        self.profiles.pop(profile_id, None)
        self.preferences = {
            key: value
            for key, value in self.preferences.items()
            if key[0] != profile_id
        }
        if self.active == profile_id:
            self.active = None

    def set_active_profile(self, profile_id: str) -> None:
        if profile_id not in self.profiles:
            raise LookupError("Profile not found.")
        self.active = profile_id

    def active_profile_id(self) -> str | None:
        return self.active

    def set_preference(self, preference: UserPreference) -> None:
        self.preferences[(preference.profile_id, preference.key)] = preference

    def list_preferences(self, profile_id: str) -> tuple[UserPreference, ...]:
        return tuple(
            sorted(
                (
                    item
                    for (owner, _), item in self.preferences.items()
                    if owner == profile_id
                ),
                key=lambda item: item.key,
            )
        )

    def delete_preferences(
        self, profile_id: str, category: PreferenceCategory | None = None
    ) -> None:
        self.preferences = {
            key: value
            for key, value in self.preferences.items()
            if not (
                key[0] == profile_id
                and (category is None or value.category is category)
            )
        }


class SqlitePreferenceRepository:
    def __init__(self, factory: DatabaseConnectionFactory) -> None:
        self.factory = factory

    def save_profile(self, profile: UserProfile) -> None:
        with self.factory.connect() as connection:
            connection.execute(
                """INSERT INTO user_profiles
                   (profile_id,name,is_default,created_at,updated_at)
                   VALUES (?,?,?,?,?) ON CONFLICT(profile_id) DO UPDATE SET
                   name=excluded.name,updated_at=excluded.updated_at""",
                (
                    profile.profile_id,
                    profile.name,
                    int(profile.is_default),
                    profile.created_at.isoformat(),
                    profile.updated_at.isoformat(),
                ),
            )

    def list_profiles(self) -> tuple[UserProfile, ...]:
        with self.factory.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM user_profiles ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return tuple(self._profile(row) for row in rows)

    def get_profile(self, profile_id: str) -> UserProfile | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                "SELECT * FROM user_profiles WHERE profile_id=?", (profile_id,)
            ).fetchone()
        return None if row is None else self._profile(row)

    def delete_profile(self, profile_id: str) -> None:
        with self.factory.connect() as connection:
            connection.execute(
                "DELETE FROM user_profiles WHERE profile_id=? AND is_default=0",
                (profile_id,),
            )

    def set_active_profile(self, profile_id: str) -> None:
        with self.factory.connect() as connection:
            connection.execute(
                "UPDATE profile_activation SET profile_id=?,updated_at=? "
                "WHERE singleton=1",
                (profile_id, utc_now().isoformat()),
            )

    def active_profile_id(self) -> str | None:
        with self.factory.connect() as connection:
            row = connection.execute(
                "SELECT profile_id FROM profile_activation WHERE singleton=1"
            ).fetchone()
        return None if row is None or row[0] is None else str(row[0])

    def set_preference(self, preference: UserPreference) -> None:
        value_json = json.dumps(
            preference.value, ensure_ascii=False, separators=(",", ":")
        )
        with self.factory.connect() as connection:
            connection.execute(
                """INSERT INTO preference_values
                   (profile_id,preference_key,category,value_json,updated_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(profile_id,preference_key) DO UPDATE SET
                   category=excluded.category,value_json=excluded.value_json,
                   updated_at=excluded.updated_at""",
                (
                    preference.profile_id,
                    preference.key,
                    preference.category.value,
                    value_json,
                    preference.updated_at.isoformat(),
                ),
            )

    def list_preferences(self, profile_id: str) -> tuple[UserPreference, ...]:
        with self.factory.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM preference_values WHERE profile_id=? "
                "ORDER BY preference_key",
                (profile_id,),
            ).fetchall()
        return tuple(
            UserPreference(
                profile_id,
                str(row["preference_key"]),
                json.loads(str(row["value_json"])),
                PreferenceCategory(str(row["category"])),
            )
            for row in rows
        )

    def delete_preferences(
        self, profile_id: str, category: PreferenceCategory | None = None
    ) -> None:
        with self.factory.connect() as connection:
            if category is None:
                connection.execute(
                    "DELETE FROM preference_values WHERE profile_id=?", (profile_id,)
                )
            else:
                connection.execute(
                    "DELETE FROM preference_values WHERE profile_id=? AND category=?",
                    (profile_id, category.value),
                )

    @staticmethod
    def _profile(row: Mapping[str, object]) -> UserProfile:
        from datetime import datetime

        return UserProfile(
            str(row["name"]),
            str(row["profile_id"]),
            bool(row["is_default"]),
            datetime.fromisoformat(str(row["created_at"])),
            datetime.fromisoformat(str(row["updated_at"])),
        )
