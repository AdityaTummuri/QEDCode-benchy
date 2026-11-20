import pytest

from timekit.durations import parse_duration


def test_seconds():
    assert parse_duration("45s") == 45


def test_hours():
    assert parse_duration("2h") == 7200


def test_garbage_is_rejected():
    with pytest.raises(ValueError):
        parse_duration("soon")
