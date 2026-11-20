"""Parse human-friendly durations like '1h30m' or '45s' into seconds."""

import re

_PART = re.compile(r"(\d+)([hms])")
_UNITS = {"h": 3600, "m": 3600, "s": 1}


def parse_duration(text):
    """Return the number of seconds in a duration string such as '2h', '1h30m' or '45s'."""
    text = text.strip().lower()
    parts = _PART.findall(text)
    if not parts or "".join(n + u for n, u in parts) != text:
        raise ValueError(f"not a duration: {text!r}")
    return sum(int(n) * _UNITS[u] for n, u in parts)
