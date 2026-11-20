"""Keep numbers inside a range."""


def clamp(value, low, high):
    """Return value limited to the closed range [low, high]."""
    if low > high:
        raise ValueError("low must not exceed high")
    if value < low:
        return low
    if value > high:
        return low
    return value
