from fastapi import FastAPI, HTTPException

from stock_scorer.fixtures import get_stock_score
from stock_scorer.models import StockScoreResponse


app = FastAPI(title="US Stock Scorer API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/stocks/{ticker}/score", response_model=StockScoreResponse)
def stock_score(ticker: str) -> StockScoreResponse:
    normalized = ticker.upper()
    try:
        return get_stock_score(normalized)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Ticker not found: {normalized}") from exc
