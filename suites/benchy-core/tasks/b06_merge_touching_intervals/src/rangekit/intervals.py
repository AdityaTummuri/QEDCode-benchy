"""Merge overlapping closed intervals."""


def merge(intervals):
    """Merge overlapping (start, end) intervals; return them sorted by start."""
    merged = []
    for start, end in sorted(intervals):
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged
