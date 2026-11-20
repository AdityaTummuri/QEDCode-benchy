from rangekit.intervals import merge


def test_touching_intervals_are_merged():
    assert merge([(1, 2), (2, 3)]) == [(1, 3)]


def test_chain_of_touching_intervals():
    assert merge([(5, 6), (1, 3), (3, 5)]) == [(1, 6)]


def test_contained_interval():
    assert merge([(1, 10), (2, 3)]) == [(1, 10)]
