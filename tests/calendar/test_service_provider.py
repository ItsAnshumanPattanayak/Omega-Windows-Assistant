from datetime import timedelta
from uuid import uuid4

import pytest

from omega.calendar import (
    CalendarEvent,
    CalendarNotFoundError,
    CalendarProviderTimeout,
    CalendarSearchCriteria,
    CalendarValidationError,
    EventUpdateRequest,
    InvitationResponse,
)


def _criteria(now):
    return CalendarSearchCriteria(now, now + timedelta(days=1))


def test_fake_provider_is_zero_network_and_lists_bounded(
    service, provider, now
) -> None:
    page = service.list_events(uuid4(), _criteria(now))
    assert [item.event_id for item in page.items] == ["event-1", "event-2"]
    assert provider.network_operations == 0


def test_search_selection_and_agenda(service, now) -> None:
    session = uuid4()
    criteria = CalendarSearchCriteria(now, now + timedelta(days=1), "Lunch")
    service.search(session, criteria)
    assert service.read_event(session, 1).event_id == "event-2"
    assert "Lunch" in service.agenda(session, _criteria(now))


def test_new_result_set_invalidates_current_selection(service, now) -> None:
    session = uuid4()
    service.list_events(session, _criteria(now))
    service.read_event(session, 1)
    service.search(
        session, CalendarSearchCriteria(now, now + timedelta(days=1), "none")
    )
    with pytest.raises(CalendarNotFoundError):
        service.read_event(session)


def test_session_selections_are_independent(service, now) -> None:
    first, second = uuid4(), uuid4()
    service.list_events(first, _criteria(now))
    with pytest.raises(CalendarNotFoundError):
        service.read_event(second, 1)


def test_availability_exposes_busy_intervals(service, now) -> None:
    assert len(service.availability(_criteria(now))) == 2
    free = service.free_intervals(_criteria(now))
    assert free and all(item.status.value == "free" for item in free)


def test_proposal_before_create_and_duplicate_prevention(
    service, provider, now
) -> None:
    session = uuid4()
    event = CalendarEvent(
        "primary",
        "New",
        now + timedelta(hours=6),
        now + timedelta(hours=7),
        timezone_name="Asia/Calcutta",
    )
    proposal = service.propose_create(session, event)
    assert proposal.event.title == "New" and provider.create_count == 0
    service.commit_create(session, "create-op")
    assert provider.create_count == 1
    with pytest.raises(CalendarNotFoundError):
        service.commit_create(session, "again")


def test_update_delete_and_invitation_receipts(service, provider, now) -> None:
    session = uuid4()
    service.list_events(session, _criteria(now))
    event = service.read_event(session, 1)
    service.propose_update(session, EventUpdateRequest(event.event_id, title="Updated"))
    service.commit_update(session, "update-op")
    assert provider.update_count == 1
    service.respond(session, InvitationResponse.ACCEPTED, "respond-op")
    assert provider.response_count == 1
    service.delete_selected(session, None, "delete-op")
    assert provider.delete_count == 1


def test_timeout_is_ambiguous_and_not_retried(service, provider, now) -> None:
    session = uuid4()
    event = CalendarEvent(
        "primary",
        "New",
        now + timedelta(hours=6),
        now + timedelta(hours=7),
        timezone_name="Asia/Calcutta",
    )
    service.propose_create(session, event)
    provider.timeout_next_mutation = True
    with pytest.raises(CalendarProviderTimeout):
        service.commit_create(session, "timeout-op")
    with pytest.raises(CalendarValidationError):
        service.commit_create(session, "timeout-op")
    assert provider.create_count == 0


def test_clear_session_discards_proposals(service, now) -> None:
    session = uuid4()
    event = CalendarEvent(
        "primary",
        "New",
        now + timedelta(hours=6),
        now + timedelta(hours=7),
        timezone_name="Asia/Calcutta",
    )
    service.propose_create(session, event)
    service.clear_session(session)
    with pytest.raises(CalendarNotFoundError):
        service.selected_create_proposal(session)
