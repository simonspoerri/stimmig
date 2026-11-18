from stimmig_pipeline.verbatim import is_verbatim

TEXT = "Die Zahl der Beispiele ist seit 2010 um 40 Prozent gestiegen. Das ist «unfair»."


def test_tolerates_whitespace_and_typography_only() -> None:
    assert is_verbatim("seit  2010 um\n40 Prozent", TEXT)
    assert is_verbatim('Das ist "unfair".', TEXT)
    assert not is_verbatim("seit 2010 um 50 Prozent", TEXT)


def test_empty_quote_never_matches() -> None:
    assert not is_verbatim("   ", TEXT)
