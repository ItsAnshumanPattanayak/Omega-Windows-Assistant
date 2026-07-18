from datetime import datetime

from omega.session.greeting import greeting_for


def test_greeting_time_ranges() -> None:
    assert greeting_for("Anshuman", datetime(2026, 1, 1, 5)).startswith("Good morning")
    assert greeting_for("Anshuman", datetime(2026, 1, 1, 12)).startswith(
        "Good afternoon"
    )
    assert greeting_for("Anshuman", datetime(2026, 1, 1, 17)).startswith("Good evening")
    assert (
        greeting_for("Sam", datetime(2026, 1, 1, 0))
        == "Good evening, Sam. How's your day going? How can I help you?"
    )
