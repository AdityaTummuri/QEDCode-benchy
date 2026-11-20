from timekit.durations import parse_duration


def test_minutes():
    assert parse_duration("10m") == 600


def test_hours_and_minutes():
    assert parse_duration("1h30m") == 5400


def test_all_units():
    assert parse_duration("1H1M1S") == 3661
