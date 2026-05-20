from stock_scorer.scoring import classify_medium_term_score


def test_classify_medium_term_score_strong():
    assert classify_medium_term_score(82) == "strong"
