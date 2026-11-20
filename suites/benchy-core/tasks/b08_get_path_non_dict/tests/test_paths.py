from datakit.paths import get_path


def test_existing_path():
    assert get_path({"a": {"b": 1}}, "a.b") == 1


def test_missing_key_gives_default():
    assert get_path({"a": {}}, "a.b", "none") == "none"


def test_top_level():
    assert get_path({"x": 3}, "x") == 3
