from datakit.paths import get_path


def test_number_in_the_middle():
    assert get_path({"a": 5}, "a.b", "d") == "d"


def test_string_in_the_middle():
    assert get_path({"a": "text"}, "a.b") is None


def test_list_in_the_middle():
    assert get_path({"a": [1, 2]}, "a.b.c", 0) == 0
