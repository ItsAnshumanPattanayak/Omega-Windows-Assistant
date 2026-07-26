from datetime import UTC, datetime, timedelta

import pytest

from omega.calendar import (
    CalendarConfiguration,
    CalendarEvent,
    CalendarService,
    FakeCalendarProvider,
)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 7, 26, 6, 0, tzinfo=UTC)


@pytest.fixture
def events(now: datetime) -> tuple[CalendarEvent, ...]:
    return (
        CalendarEvent(
            "primary",
            "Planning",
            now + timedelta(hours=1),
            now + timedelta(hours=2),
            event_id="event-1",
            location="Room 1",
            timezone_name="Asia/Calcutta",
        ),
        CalendarEvent(
            "primary",
            "Lunch",
            now + timedelta(hours=4),
            now + timedelta(hours=5),
            event_id="event-2",
            timezone_name="Asia/Calcutta",
        ),
    )


@pytest.fixture
def configuration() -> CalendarConfiguration:
    return CalendarConfiguration(
        enabled=True,
        provider="fake",
        account_name="test",
        timezone_name="Asia/Calcutta",
    )


@pytest.fixture
def provider(events: tuple[CalendarEvent, ...]) -> FakeCalendarProvider:
    return FakeCalendarProvider(events)


@pytest.fixture
def service(
    configuration: CalendarConfiguration, provider: FakeCalendarProvider
) -> CalendarService:
    return CalendarService(configuration, provider)
