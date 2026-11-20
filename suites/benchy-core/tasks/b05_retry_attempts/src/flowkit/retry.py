"""Call flaky functions again when they fail."""


def retry(fn, attempts=3, exceptions=(Exception,)):
    """Call fn() up to `attempts` times; return its first result or re-raise the last error."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last_error = None
    for _ in range(attempts - 1):
        try:
            return fn()
        except exceptions as exc:
            last_error = exc
    if last_error is None:
        return fn()
    raise last_error
