import pytest

from flowkit.retry import retry


def test_success_on_first_call():
    assert retry(lambda: 42) == 42


def test_attempts_must_be_positive():
    with pytest.raises(ValueError):
        retry(lambda: 1, attempts=0)
