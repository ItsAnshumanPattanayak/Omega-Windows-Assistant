import logging

import pytest

from omega.core.exceptions import SecurityValidationError
from omega.security.payloads import JsonSecurityLimits, load_bounded_json
from omega.security.redaction import redact_text, redact_value
from omega.utils.logger import RedactingFormatter


def test_bounded_json_accepts_normal_json() -> None:
    assert load_bounded_json(
        b'{"name":"Omega","items":[1,true,null]}', JsonSecurityLimits(200)
    ) == {"name": "Omega", "items": [1, True, None]}


@pytest.mark.parametrize(
    "raw,limits",
    [
        ('{"key":1,"key":2}', JsonSecurityLimits(100)),
        ("[[[[0]]]]", JsonSecurityLimits(100, maximum_depth=2)),
        ("[1,2,3]", JsonSecurityLimits(100, maximum_items=2)),
        ('{"large":"value"}', JsonSecurityLimits(8)),
        ('{"value":NaN}', JsonSecurityLimits(100)),
    ],
)
def test_bounded_json_rejects_ambiguous_or_excessive_payloads(
    raw: str, limits: JsonSecurityLimits
) -> None:
    with pytest.raises(SecurityValidationError):
        load_bounded_json(raw, limits)


def test_redaction_covers_credentials_and_nested_values() -> None:
    text = "password=hunter2 Authorization: Bearer abc.def token=secret-value"
    redacted = redact_text(text)
    assert "hunter2" not in redacted
    assert "abc.def" not in redacted
    assert "secret-value" not in redacted
    nested = redact_value({"password": "visible", "nested": [text]})
    assert nested["password"] == "[REDACTED]"
    assert "visible" not in str(nested)


def test_logging_formatter_redacts_exception_text() -> None:
    formatter = RedactingFormatter("%(levelname)s %(message)s")
    try:
        raise RuntimeError("api_key=private-value")
    except RuntimeError:
        record = logging.LogRecord(
            "omega", logging.ERROR, __file__, 1, "failed password=hidden", (), None
        )
        record.exc_info = __import__("sys").exc_info()
    output = formatter.format(record)
    assert "private-value" not in output
    assert "hidden" not in output
    assert "[REDACTED]" in output
