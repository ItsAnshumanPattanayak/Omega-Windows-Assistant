from pathlib import Path

import pytest

from omega.core.exceptions import ProtectedResourceError
from omega.models import IntentType
from omega.safety import ProtectedResourceConfiguration, ProtectedResourceEvaluator


def test_resolved_protected_path_is_denied_but_same_named_user_folder_is_allowed(
    context_factory, tmp_path: Path
):
    protected = tmp_path / "omega" / "config"
    protected.mkdir(parents=True)
    user_config = tmp_path / "Desktop" / "config"
    user_config.mkdir(parents=True)
    evaluator = ProtectedResourceEvaluator((protected,))

    denied = evaluator.evaluate(context_factory(destination_path=protected / "x.txt"))
    allowed = evaluator.evaluate(
        context_factory(destination_path=user_config / "x.txt")
    )

    assert denied.denied and denied.reason_code == "PROTECTED_PATH"
    assert not allowed.denied


@pytest.mark.parametrize(
    "value,code",
    [
        (r"..\..\Windows\test.txt", "PATH_TRAVERSAL_REJECTED"),
        (r"C:\Windows\test.txt", "ABSOLUTE_PATH_REJECTED"),
        (r"\\server\share\test.txt", "SPECIAL_PATH_REJECTED"),
        (r"\\?\C:\Windows\test.txt", "SPECIAL_PATH_REJECTED"),
        ("file.txt:secret", "ALTERNATE_STREAM_REJECTED"),
        (r"%WINDIR%\test.txt", "PATH_EXPANSION_REJECTED"),
        ("~/test.txt", "PATH_EXPANSION_REJECTED"),
    ],
)
def test_special_and_escape_paths_fail_closed(context_factory, value, code):
    context = context_factory(parameters={"file_name": value})
    result = ProtectedResourceEvaluator(()).evaluate(context)
    assert result.denied and result.reason_code == code


def test_blocked_application_close_is_denied(context_factory):
    context = context_factory(
        IntentType.CLOSE_APPLICATION,
        application_id="file_explorer",
        parameters={"application_id": "file_explorer"},
    )
    result = ProtectedResourceEvaluator(()).evaluate(context)
    assert result.denied and result.reason_code == "PROTECTED_APPLICATION"


def test_symlink_escape_is_denied_when_supported(context_factory, tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "approved" / "linked"
    link.parent.mkdir()
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlink creation is unavailable on this host.")
    result = ProtectedResourceEvaluator(()).evaluate(
        context_factory(destination_path=link / "file.txt")
    )
    assert result.denied and result.reason_code == "LINKED_PATH_REJECTED"


def test_protected_resource_configuration_is_typed_and_rejects_duplicates(
    tmp_path: Path,
):
    valid = tmp_path / "protected.json"
    valid.write_text(
        '{"protected_locations":["C:\\\\Windows"],'
        '"protected_project_paths":[".git"],'
        '"protected_processes":["System"]}',
        encoding="utf-8",
    )
    configuration = ProtectedResourceConfiguration.from_file(valid)
    assert configuration.protected_processes == frozenset({"System"})

    invalid = tmp_path / "invalid.json"
    invalid.write_text(
        '{"protected_locations":["C:\\\\Windows","C:\\\\Windows"],'
        '"protected_project_paths":[],"protected_processes":[]}',
        encoding="utf-8",
    )
    with pytest.raises(ProtectedResourceError, match="duplicates"):
        ProtectedResourceConfiguration.from_file(invalid)
