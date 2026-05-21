import os

from stock_scorer.fixtures import get_stock_score as get_fixture_stock_score
from stock_scorer.live_scoring import build_score_from_market_snapshot
from stock_scorer.market_data import AlphaVantageClient, FmpClient, MarketDataConfigurationError
from stock_scorer.models import StockScoreResponse


def get_stock_score(ticker: str) -> StockScoreResponse:
    source = os.getenv("STOCK_SCORER_DATA_SOURCE", "fixture").strip().lower()
    if source in {"fixture", "fixtures"}:
        return get_fixture_stock_score(ticker)
    if source in {"alpha_vantage", "alphavantage"}:
        return get_alpha_vantage_stock_score(ticker)
    if source == "fmp":
        return get_fmp_stock_score(ticker)
    raise MarketDataConfigurationError(f"Unsupported STOCK_SCORER_DATA_SOURCE: {source}")


def get_alpha_vantage_stock_score(ticker: str) -> StockScoreResponse:
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    with AlphaVantageClient(api_key=api_key) as client:
        snapshot = client.fetch_snapshot(ticker)
    return build_score_from_market_snapshot(snapshot)


def get_fmp_stock_score(ticker: str) -> StockScoreResponse:
    api_key = os.getenv("FMP_API_KEY", "")
    with FmpClient(api_key=api_key) as client:
        snapshot = client.fetch_snapshot(ticker)
    return build_score_from_market_snapshot(snapshot)
