from typing import Any

from pydantic import BaseModel

from stock_scorer.models import StockScoreResponse


class ProviderHealth(BaseModel):
    name: str
    api_key_configured: bool
    active: bool


class ProviderStatusResponse(BaseModel):
    active_source: str
    providers: dict[str, ProviderHealth]


class RawTickerDataResponse(BaseModel):
    ticker: str
    source: str
    raw: dict[str, Any]


class RefreshTickerResponse(BaseModel):
    ticker: str
    status: str
    score: StockScoreResponse
