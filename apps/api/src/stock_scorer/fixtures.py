import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from stock_scorer.models import FactorScore, StockScoreResponse
from stock_scorer.scoring import classify_medium_term_score, classify_short_term_state, decide_action


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "stocks.json"


@lru_cache(maxsize=1)
def load_fixture_data() -> dict[str, Any]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_stock_score(ticker: str) -> StockScoreResponse:
    normalized = ticker.upper()
    data = load_fixture_data()
    if normalized not in data:
        raise KeyError(f"Ticker not found in fixture data: {normalized}")

    row = data[normalized]
    medium_label = classify_medium_term_score(row["medium_term_score"])
    short_label = classify_short_term_state(
        score=row["short_term_score"],
        overheated=row["overheated"],
        broken_trend=row["broken_trend"],
    )
    decision = decide_action(medium_label, short_label)

    return StockScoreResponse(
        ticker=row["ticker"],
        company_name=row["company_name"],
        last_price=row["last_price"],
        medium_term_score=row["medium_term_score"],
        medium_term_label=medium_label,
        short_term_score=row["short_term_score"],
        short_term_label=short_label,
        factors=[FactorScore(**factor) for factor in row["factors"]],
        decision=decision,
        data_as_of=row["data_as_of"],
    )


def get_raw_fixture_stock(ticker: str) -> dict[str, Any]:
    normalized = ticker.upper()
    data = load_fixture_data()
    if normalized not in data:
        raise KeyError(f"Ticker not found in fixture data: {normalized}")
    return dict(data[normalized])
