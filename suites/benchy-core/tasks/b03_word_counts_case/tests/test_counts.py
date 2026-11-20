from textkit.counts import word_counts


def test_simple_counts():
    assert word_counts("a b a") == {"a": 2, "b": 1}


def test_punctuation_is_ignored():
    assert word_counts("hi, hi!") == {"hi": 2}


def test_empty_text():
    assert word_counts("") == {}
