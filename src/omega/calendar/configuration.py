"""Conservative, credential-free calendar configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from omega.calendar.exceptions import CalendarConfigurationError


@dataclass(frozen=True)
class CalendarConfiguration:
    """Validated calendar limits; credentials are deliberately absent."""

    enabled: bool = False
    provider: str | None = None
    account_name: str | None = None
    timezone_name: str = "UTC"
    maximum_events_per_request: int = 50
    maximum_search_query_characters: int = 300
    maximum_date_range_days: int = 366
    maximum_title_characters: int = 300
    maximum_description_characters: int = 10_000
    maximum_location_characters: int = 500
    maximum_attendees: int = 50
    maximum_recurrence_occurrences: int = 500
    default_event_duration_minutes: int = 60
    minimum_event_duration_minutes: int = 5
    maximum_event_duration_hours: int = 24
    working_day_start: str = "09:00"
    working_day_end: str = "18:00"
    minimum_free_slot_minutes: int = 30
    maximum_reminders: int = 5
    maximum_reminder_lead_days: int = 30
    provider_timeout_seconds: float = 20.0
    require_confirmation_for_create: bool = True
    require_confirmation_for_update: bool = True
    require_confirmation_for_delete: bool = True
    require_confirmation_for_invitation_response: bool = True

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> CalendarConfiguration:
        unknown = set(values).difference(cls.__dataclass_fields__)
        if unknown:
            raise CalendarConfigurationError(
                "Unknown calendar setting(s): " + ", ".join(sorted(unknown))
            )
        try:
            return cls(**values)
        except TypeError as error:
            raise CalendarConfigurationError(
                "Calendar configuration is invalid."
            ) from error

    def __post_init__(self) -> None:
        booleans = (
            "enabled",
            "require_confirmation_for_create",
            "require_confirmation_for_update",
            "require_confirmation_for_delete",
            "require_confirmation_for_invitation_response",
        )
        if any(not isinstance(getattr(self, name), bool) for name in booleans):
            raise CalendarConfigurationError("Calendar policy flags must be booleans.")
        if self.enabled and not (self.provider and self.provider.strip()):
            raise CalendarConfigurationError(
                "calendar.provider is required when calendar is enabled."
            )
        if self.provider not in {None, "fake"}:
            raise CalendarConfigurationError("calendar.provider is not supported.")
        if self.account_name is not None and not self.account_name.strip():
            raise CalendarConfigurationError("calendar.account_name cannot be empty.")
        try:
            ZoneInfo(self.timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise CalendarConfigurationError(
                "calendar.timezone_name is invalid."
            ) from error
        bounds = {
            "maximum_events_per_request": (1, 200),
            "maximum_search_query_characters": (1, 2_000),
            "maximum_date_range_days": (1, 366),
            "maximum_title_characters": (1, 1_000),
            "maximum_description_characters": (1, 100_000),
            "maximum_location_characters": (1, 2_000),
            "maximum_attendees": (1, 200),
            "maximum_recurrence_occurrences": (1, 500),
            "default_event_duration_minutes": (5, 1_440),
            "minimum_event_duration_minutes": (1, 1_440),
            "maximum_event_duration_hours": (1, 168),
            "minimum_free_slot_minutes": (5, 1_440),
            "maximum_reminders": (1, 10),
            "maximum_reminder_lead_days": (1, 30),
        }
        for name, (minimum, maximum) in bounds.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                raise CalendarConfigurationError(
                    f"calendar.{name} must be between {minimum} and {maximum}."
                )
        timeout = self.provider_timeout_seconds
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 1 <= timeout <= 120
        ):
            raise CalendarConfigurationError(
                "calendar.provider_timeout_seconds must be between 1 and 120."
            )
        if not all(getattr(self, name) for name in booleans[1:]):
            raise CalendarConfigurationError(
                "Calendar mutation confirmations must remain enabled."
            )
        try:
            start = time.fromisoformat(self.working_day_start)
            end = time.fromisoformat(self.working_day_end)
        except ValueError as error:
            raise CalendarConfigurationError(
                "Calendar working hours must use HH:MM time."
            ) from error
        if end <= start:
            raise CalendarConfigurationError(
                "calendar.working_day_end must be after working_day_start."
            )
        if not (
            self.minimum_event_duration_minutes
            <= self.default_event_duration_minutes
            <= self.maximum_event_duration_hours * 60
        ):
            raise CalendarConfigurationError(
                "Default event duration is outside configured limits."
            )
