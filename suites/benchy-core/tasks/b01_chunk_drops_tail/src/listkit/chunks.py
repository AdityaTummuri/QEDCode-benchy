"""Split sequences into fixed-size groups."""


def chunk(items, size):
    """Split `items` into lists of `size` items; the last list may be shorter."""
    if size < 1:
        raise ValueError("size must be at least 1")
    items = list(items)
    return [items[i : i + size] for i in range(0, len(items) - size + 1, size)]
