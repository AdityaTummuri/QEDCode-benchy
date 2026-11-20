import pytest

from numkit.bounds import clamp


def test_inside_range_is_unchanged():
    assert clamp(5, 0, 10) == 5


def test_below_range_goes_to_low():
    assert clamp(-3, 0, 10) == 0


def test_bad_range():
    with pytest.raises(ValueError):
        clamp(1, 5, 2)
