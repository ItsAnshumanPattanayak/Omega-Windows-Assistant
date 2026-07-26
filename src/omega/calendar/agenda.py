"""Deterministic, local calendar summaries."""

from zoneinfo import ZoneInfo

from omega.calendar.models import CalendarEvent, EventVisibility


def format_event(event: CalendarEvent, timezone_name: str) -> str:
    zone = ZoneInfo(timezone_name)
    if event.all_day:
        when = f"{event.start_at.astimezone(zone):%Y-%m-%d} (all day)"
    else:
        start = event.start_at.astimezone(zone)
        end = event.end_at.astimezone(zone)
        when = f"{start:%Y-%m-%d %H:%M}–{end:%H:%M} {timezone_name}"
    private = event.visibility in {
        EventVisibility.PRIVATE,
        EventVisibility.CONFIDENTIAL,
    }
    title = "Private event" if private else event.title
    location = f" — {event.location}" if event.location and not private else ""
    return f"{when} — {title}{location}"


def summarize_agenda(events: tuple[CalendarEvent, ...], timezone_name: str) -> str:
    if not events:
        return "No calendar events were found."
    return "\n".join(
        f"{index}. {format_event(item, timezone_name)}"
        for index, item in enumerate(events, 1)
    )
