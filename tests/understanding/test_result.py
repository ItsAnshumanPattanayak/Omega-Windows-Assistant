from omega.understanding import CommandParser


def test_parse_result_serialization_has_no_regex_or_callable_values() -> None:
    data = CommandParser().parse("Open Chrome").to_dict()
    assert data["matched"] is True
    assert data["matched_pattern"] == "open"
    assert data["command"]["intent"] == "open_application"
