from omega.understanding.patterns import INTENT_PATTERNS


def test_patterns_are_named_ordered_and_compiled_once() -> None:
    names = [pattern.name for pattern in INTENT_PATTERNS]
    assert len(names) == len(set(names))
    assert names.index("app_status") < names.index("open")
