from stock_scorer.models import ActionDecision, HorizonLabel, ShortTermLabel
from stock_scorer.scoring import (
    classify_medium_term_score,
    classify_short_term_state,
    decide_action,
)


def test_classify_medium_term_score_strong():
    assert classify_medium_term_score(82) == HorizonLabel.STRONG


def test_classify_medium_term_score_weak():
    assert classify_medium_term_score(42) == HorizonLabel.WEAK


def test_classify_short_term_wait_pullback_when_overheated():
    assert classify_short_term_state(score=74, overheated=True, broken_trend=False) == ShortTermLabel.WAIT_PULLBACK


def test_decide_action_strong_medium_and_wait_pullback():
    decision = decide_action(HorizonLabel.STRONG, ShortTermLabel.WAIT_PULLBACK)

    assert decision.action == ActionDecision.WAIT
    assert "不追高" in decision.summary
