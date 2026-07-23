from datetime import UTC, datetime
from uuid import uuid4

from omega.gui.formatting import format_activity, format_timestamp
from omega.history import HistoryActivity


def test_activity_formatting_is_bounded_and_exposes_status():
    item = HistoryActivity(
        "action",
        uuid4(),
        datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        "open_application: failed " + ("x" * 300),
    )

    formatted = format_activity(item)

    assert len(formatted.summary) == 180
    assert formatted.summary.endswith("…")
    assert format_timestamp(item.occurred_at)


def test_command_activity_has_no_synthetic_status():
    item = HistoryActivity(
        "command",
        uuid4(),
        datetime.now(UTC),
        "Open Chrome",
    )

    assert format_activity(item).status == ""
