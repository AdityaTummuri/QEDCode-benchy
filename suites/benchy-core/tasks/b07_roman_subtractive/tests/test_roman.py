import pytest

from numkit.roman import to_roman


def test_simple_numbers():
    assert to_roman(1) == "I"
    assert to_roman(3) == "III"
    assert to_roman(5) == "V"
    assert to_roman(20) == "XX"


def test_out_of_range():
    with pytest.raises(ValueError):
        to_roman(0)
