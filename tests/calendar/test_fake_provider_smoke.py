"""Safe, zero-network Phase 19 smoke workflow."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from omega.calendar import (
    CalendarConfiguration,
    CalendarEvent,
    CalendarReminder,
    CalendarSearchCriteria,
    CalendarService,
    CalendarValidationError,
    EventUpdateRequest,
    FakeCalendarProvider,
    RecurrenceFrequency,
    RecurrenceRule,
)


def test_complete_fake_provider_smoke() -> None:
    now = datetime(2026, 7, 26, 6, tzinfo=UTC)
    seeded = (
        CalendarEvent(
            "primary",
            "India planning",
            now + timedelta(hours=1),
            now + timedelta(hours=2),
            event_id="india",
            timezone_name="Asia/Calcutta",
        ),
        CalendarEvent(
            "primary",
            "New York review",
            now + timedelta(hours=3),
            now + timedelta(hours=4),
            event_id="new-york",
            timezone_name="America/New_York",
        ),
    )
    provider = FakeCalendarProvider(seeded)
    service = CalendarService(
        CalendarConfiguration(
            enabled=True, provider="fake", timezone_name="Asia/Calcutta"
        ),
        provider,
    )
    session = uuid4()
    criteria = CalendarSearchCriteria(now, now + timedelta(days=1))
    assert len(service.list_events(session, criteria).items) == 2
    assert (
        service.search(
            session, CalendarSearchCriteria(now, now + timedelta(days=1), "York")
        )
        .items[0]
        .event_id
        == "new-york"
    )
    assert service.read_event(session, 1).title == "New York review"
    assert service.availability(criteria)
    assert service.free_intervals(criteria)

    proposed = CalendarEvent(
        "primary",
        "Proposed event",
        now + timedelta(hours=5),
        now + timedelta(hours=6),
        timezone_name="Asia/Calcutta",
        reminders=(CalendarReminder(30),),
    )
    service.propose_create(session, proposed)
    assert provider.create_count == 0
    service.commit_create(session, "create-smoke")
    assert provider.create_count == 1

    service.list_events(session, criteria)
    created_index = next(
        index
        for index, item in enumerate(service.list_events(session, criteria).items, 1)
        if item.event_id == proposed.event_id
    )
    service.read_event(session, created_index)
    service.propose_update(
        session, EventUpdateRequest(proposed.event_id, title="Updated proposal")
    )
    service.commit_update(session, "update-smoke")
    assert provider.read_event(proposed.event_id).title == "Updated proposal"

    recurring = CalendarEvent(
        "primary",
        "Weekly review",
        now + timedelta(days=1),
        now + timedelta(days=1, hours=1),
        timezone_name="Asia/Calcutta",
        recurrence=RecurrenceRule(RecurrenceFrequency.WEEKLY, weekdays=(0,), count=4),
    )
    service.propose_create(session, recurring)
    service.commit_create(session, "create-recurring-smoke")
    service.list_events(session, CalendarSearchCriteria(now, now + timedelta(days=2)))
    recurring_index = next(
        index
        for index, item in enumerate(
            service.list_events(
                session, CalendarSearchCriteria(now, now + timedelta(days=2))
            ).items,
            1,
        )
        if item.event_id == recurring.event_id
    )
    service.read_event(session, recurring_index)
    with pytest.raises(CalendarValidationError):
        service.propose_update(
            session, EventUpdateRequest(recurring.event_id, title="Unsafe scope")
        )
    assert "Updated proposal" in service.agenda(session, criteria)

    service.list_events(session, criteria)
    created_index = next(
        index
        for index, item in enumerate(service.list_events(session, criteria).items, 1)
        if item.event_id == proposed.event_id
    )
    service.read_event(session, created_index)
    service.delete_selected(session, None, "delete-smoke")
    assert provider.delete_count == 1 and provider.network_operations == 0
