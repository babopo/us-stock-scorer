import os

from stock_scorer.fixtures import get_stock_score as get_fixture_stock_score
from stock_scorer.live_scoring import build_score_from_market_snapshot
from stock_scorer.market_data import (
    AlphaVantageClient,
    FinnhubClient,
    FmpClient,
    MarketDataConfigurationError,
    MarketDataError,
    MarketDataNotFound,
    MarketDataUnavailable,
)
from stock_scorer.models import StockScoreResponse


def get_stock_score(ticker: str) -> StockScoreResponse:
    sources = get_configured_data_sources()
    failures: list[tuple[str, Exception]] = []
    for source in sources:
        try:
            return get_stock_score_from_source(source, ticker)
        except (KeyError, MarketDataError) as exc:
            failures.append((source, exc))

    if len(failures) == 1:
        raise failures[0][1]
    if all(isinstance(error, MarketDataConfigurationError) for _, error in failures):
        raise MarketDataConfigurationError(_format_fallback_failures(ticker, failures))
    if all(isinstance(error, (KeyError, MarketDataNotFound)) for _, error in failures):
        raise MarketDataNotFound(_format_fallback_failures(ticker, failures))
    raise MarketDataUnavailable(_format_fallback_failures(ticker, failures))


def get_configured_data_sources() -> list[str]:
    chain = os.getenv("STOCK_SCORER_DATA_SOURCES", "").strip()
    if chain:
        sources = [_normalize_source(source) for source in chain.split(",") if source.strip()]
        return sources or ["fixture"]
    return [_normalize_source(os.getenv("STOCK_SCORER_DATA_SOURCE", "fixture"))]


def get_active_source_label() -> str:
    return ",".join(get_configured_data_sources())


def get_stock_score_from_source(source: str, ticker: str) -> StockScoreResponse:
    source = _normalize_source(source)
    if source in {"fixture", "fixtures"}:
        return get_fixture_stock_score(ticker)
    if source in {"alpha_vantage", "alphavantage"}:
        return get_alpha_vantage_stock_score(ticker)
    if source == "fmp":
        return get_fmp_stock_score(ticker)
    if source == "finnhub":
        return get_finnhub_stock_score(ticker)
    raise MarketDataConfigurationError(f"Unsupported STOCK_SCORER_DATA_SOURCE: {source}")


def _normalize_source(source: str) -> str:
    normalized = source.strip().lower()
    return "alpha_vantage" if normalized == "alphavantage" else normalized


def _format_fallback_failures(ticker: str, failures: list[tuple[str, Exception]]) -> str:
    details = "; ".join(f"{source}: {error}" for source, error in failures)
    return f"All data sources failed for {ticker.upper()}: {details}"


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


def get_finnhub_stock_score(ticker: str) -> StockScoreResponse:
    api_key = os.getenv("FINNHUB_API_KEY", "")
    with FinnhubClient(api_key=api_key) as client:
        snapshot = client.fetch_snapshot(ticker)
    return build_score_from_market_snapshot(snapshot)
