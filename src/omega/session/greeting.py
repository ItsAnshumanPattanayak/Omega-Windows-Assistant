"""Testable, time-based greeting generation."""

from __future__ import annotations

from datetime import datetime


def greeting_for(display_name: str, current_time: datetime) -> str:
    """Return Omega's personalized greeting for the supplied local time."""
    hour = current_time.hour
    if 5 <= hour < 12:
        salutation = "Good morning"
    elif 12 <= hour < 17:
        salutation = "Good afternoon"
    else:
        salutation = "Good evening"
    return f"{salutation}, {display_name}. How's your day going? How can I help you?"
