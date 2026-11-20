import pytest

from listkit.chunks import chunk


def test_even_split():
    assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def test_empty_input():
    assert chunk([], 3) == []


def test_size_must_be_positive():
    with pytest.raises(ValueError):
        chunk([1], 0)
