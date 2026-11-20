from numkit.bounds import clamp


def test_above_range_goes_to_high():
    assert clamp(15, 0, 10) == 10


def test_floats_above_range():
    assert clamp(2.5, -1.0, 1.0) == 1.0


def test_edges_are_kept():
    assert clamp(10, 0, 10) == 10
    assert clamp(0, 0, 10) == 0
