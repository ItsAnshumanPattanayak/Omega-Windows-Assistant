"""Safe formatting helpers for GUI display."""

from __future__ import annotations

from datetime import datetime

from omega.gui.models import ActivityItem
from omega.history import HistoryActivity

_MAX_SUMMARY = 180


def format_timestamp(value: datetime) -> str:
    """Format an aware timestamp in local time without diagnostic detail."""

    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def format_activity(item: HistoryActivity) -> ActivityItem:
    """Convert a persistent activity record into a bounded view model."""

    summary = " ".join(item.summary.split())
    if len(summary) > _MAX_SUMMARY:
        summary = summary[: _MAX_SUMMARY - 1] + "…"
    status = ""
    if item.kind == "action" and ":" in summary:
        status = summary.rsplit(":", maxsplit=1)[-1].strip()
    return ActivityItem(
        identifier=str(item.identifier),
        kind=item.kind,
        summary=summary,
        status=status,
        timestamp=format_timestamp(item.occurred_at),
    )
