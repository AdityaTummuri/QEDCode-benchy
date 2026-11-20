"""Word statistics for short texts."""

import re

_WORD = re.compile(r"[A-Za-z']+")


def word_counts(text):
    """Return a dict mapping each word in `text` to how often it appears."""
    counts = {}
    for word in _WORD.findall(text):
        counts[word] = counts.get(word, 0) + 1
    return counts
