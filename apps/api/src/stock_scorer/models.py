from enum import StrEnum

from pydantic import BaseModel, Field


class HorizonLabel(StrEnum):
    STRONG = "strong"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    WEAK = "weak"
    AVOID = "avoid"


class ShortTermLabel(StrEnum):
    ENTRY = "entry"
    PROBE = "probe"
    WAIT_PULLBACK = "wait_pullback"
    WAIT_BREAKOUT = "wait_breakout"
    AVOID = "avoid"


class ActionDecision(StrEnum):
    BUY_IN_TRANCHES = "buy_in_tranches"
    SMALL_PROBE = "small_probe"
    WAIT = "wait"
    SHORT_TERM_ONLY = "short_term_only"
    AVOID = "avoid"


class FactorScore(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)
    evidence: list[str]


class Decision(BaseModel):
    action: ActionDecision
    summary: str
    trigger_conditions: list[str]
    invalidation_conditions: list[str]
    risks: list[str]


class StockScoreResponse(BaseModel):
    ticker: str
    company_name: str
    last_price: float
    medium_term_score: int = Field(ge=0, le=100)
    medium_term_label: HorizonLabel
    short_term_score: int = Field(ge=0, le=100)
    short_term_label: ShortTermLabel
    factors: list[FactorScore]
    decision: Decision
    data_as_of: str
