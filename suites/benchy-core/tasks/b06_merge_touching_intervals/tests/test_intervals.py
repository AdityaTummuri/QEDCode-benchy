from rangekit.intervals import merge


def test_overlapping_are_merged():
    assert merge([(1, 3), (2, 5)]) == [(1, 5)]


def test_disjoint_are_kept_and_sorted():
    assert merge([(6, 7), (1, 2)]) == [(1, 2), (6, 7)]


def test_empty():
    assert merge([]) == []
