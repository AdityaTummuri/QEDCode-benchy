from listkit.chunks import chunk


def test_uneven_split_keeps_the_tail():
    assert chunk([1, 2, 3], 2) == [[1, 2], [3]]


def test_size_larger_than_input():
    assert chunk("ab", 5) == [["a", "b"]]


def test_size_one():
    assert chunk((7, 8, 9), 1) == [[7], [8], [9]]
