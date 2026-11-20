from textkit.counts import word_counts


def test_case_is_ignored():
    assert word_counts("The the THE.") == {"the": 3}


def test_keys_are_lower_case():
    assert word_counts("Hello World") == {"hello": 1, "world": 1}
