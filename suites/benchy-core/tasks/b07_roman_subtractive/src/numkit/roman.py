"""Roman numerals."""

_SYMBOLS = [
    (1000, "M"),
    (500, "D"),
    (100, "C"),
    (50, "L"),
    (10, "X"),
    (5, "V"),
    (1, "I"),
]


def to_roman(number):
    """Return `number` (1 to 3999) as a Roman numeral."""
    if not 1 <= number <= 3999:
        raise ValueError("number must be between 1 and 3999")
    out = []
    for value, symbol in _SYMBOLS:
        count, number = divmod(number, value)
        out.append(symbol * count)
    return "".join(out)
