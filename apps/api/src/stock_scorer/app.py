from fastapi import FastAPI, HTTPException

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
