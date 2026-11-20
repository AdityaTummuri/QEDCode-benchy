from numkit.roman import to_roman


def test_four_and_nine():
    assert to_roman(4) == "IV"
    assert to_roman(9) == "IX"


def test_forty_ninety_and_up():
    assert to_roman(40) == "XL"
    assert to_roman(90) == "XC"
    assert to_roman(400) == "CD"
    assert to_roman(900) == "CM"


def test_mixed():
    assert to_roman(1994) == "MCMXCIV"
    assert to_roman(3999) == "MMMCMXCIX"
