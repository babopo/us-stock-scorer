import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from stock_scorer.admin_models import (
    ProviderHealth,
    ProviderStatusResponse,
    RawTickerDataResponse,
    RefreshTickerResponse,
)
from stock_scorer.fixtures import get_raw_fixture_stock
from stock_scorer.market_data import (
    MarketDataConfigurationError,
    MarketDataError,
    MarketDataNotFound,
    MarketDataRateLimited,
    MarketDataUnavailable,
)
from stock_scorer.models import StockScoreResponse
from stock_scorer.score_service import get_stock_score


app = FastAPI(title="US Stock Scorer API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["authorization", "content-type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/stocks/{ticker}/score", response_model=StockScoreResponse)
def stock_score(ticker: str) -> StockScoreResponse:
    normalized = ticker.upper()
    try:
        return get_stock_score(normalized)
    except (KeyError, MarketDataNotFound) as exc:
        raise HTTPException(status_code=404, detail=f"Ticker not found: {normalized}") from exc
    except (MarketDataConfigurationError, MarketDataRateLimited) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (MarketDataUnavailable, MarketDataError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/admin/providers/status", response_model=ProviderStatusResponse)
def admin_provider_status() -> ProviderStatusResponse:
    active_source = os.getenv("STOCK_SCORER_DATA_SOURCE", "fixture").strip().lower() or "fixture"
    return ProviderStatusResponse(
        active_source=active_source,
        providers={
            "fixture": ProviderHealth(name="fixture", api_key_configured=True, active=active_source in {"fixture", "fixtures"}),
            "fmp": ProviderHealth(
                name="fmp",
                api_key_configured=bool(os.getenv("FMP_API_KEY")),
                active=active_source == "fmp",
            ),
            "alpha_vantage": ProviderHealth(
                name="alpha_vantage",
                api_key_configured=bool(os.getenv("ALPHA_VANTAGE_API_KEY")),
                active=active_source in {"alpha_vantage", "alphavantage"},
            ),
        },
    )


@app.get("/v1/admin/stocks/{ticker}/raw-data", response_model=RawTickerDataResponse)
def admin_ticker_raw_data(ticker: str) -> RawTickerDataResponse:
    normalized = ticker.upper()
    source = os.getenv("STOCK_SCORER_DATA_SOURCE", "fixture").strip().lower() or "fixture"
    if source not in {"fixture", "fixtures"}:
        raise HTTPException(status_code=503, detail="Raw data inspection is only available for fixture data source")

    try:
        raw = get_raw_fixture_stock(normalized)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Ticker not found: {normalized}") from exc

    return RawTickerDataResponse(ticker=normalized, source="fixture", raw=raw)


@app.post("/v1/admin/stocks/{ticker}/refresh", response_model=RefreshTickerResponse)
def admin_refresh_ticker(ticker: str) -> RefreshTickerResponse:
    normalized = ticker.upper()
    return RefreshTickerResponse(ticker=normalized, status="completed", score=stock_score(normalized))
