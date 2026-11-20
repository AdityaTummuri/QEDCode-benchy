import pytest

from flowkit.retry import retry


class Flaky:
    def __init__(self, failures):
        self.failures = failures
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("not yet")
        return "ok"


def test_succeeds_on_the_last_allowed_attempt():
    fn = Flaky(failures=2)
    assert retry(fn, attempts=3) == "ok"
    assert fn.calls == 3


def test_gives_up_after_exactly_attempts_calls():
    fn = Flaky(failures=10)
    with pytest.raises(RuntimeError):
        retry(fn, attempts=4)
    assert fn.calls == 4


def test_single_attempt_raises_immediately():
    fn = Flaky(failures=1)
    with pytest.raises(RuntimeError):
        retry(fn, attempts=1)
    assert fn.calls == 1
