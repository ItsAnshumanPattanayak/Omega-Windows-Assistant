from omega.understanding import CommandNormalizer


def test_normalization_is_conservative_and_deterministic() -> None:
    normalizer = CommandNormalizer()
    assert normalizer.normalize("  Open   Chrome. ") == "open chrome"
    assert normalizer.normalize("OPEN CHROME") == "open chrome"
    assert normalizer.normalize("Create author.txt") == "create author.txt"
    assert (
        normalizer.normalize("Write “Hello World” into C:\\Notes\\a.txt")
        == 'write "hello world" into c:\\notes\\a.txt'
    )
    assert normalizer.normalize("") == ""
