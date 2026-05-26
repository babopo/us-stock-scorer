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


class BacktestRunRequest(BaseModel):
    tickers: list[str]
    start_date: str
    end_date: str
    initial_cash: float = 10_000.0


class BacktestMetricsResponse(BaseModel):
    total_return: float
    annualized_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    average_holding_days: float
    buy_hold_return: float


class BacktestTradeResponse(BaseModel):
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    shares: float
    return_pct: float
    holding_days: int
    exit_reason: str


class BacktestRunResponse(BaseModel):
    run_id: int
    strategy_id: int
    tickers: list[str]
    start_date: str
    end_date: str
    initial_cash: float
    metrics: BacktestMetricsResponse
    trades: list[BacktestTradeResponse] = []


class StoredBacktestRunResponse(BaseModel):
    run_id: int
    strategy_id: int
    tickers: list[str]
    start_date: str
    end_date: str
    initial_cash: float
    created_at: str
    total_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    buy_hold_return: float


class BacktestRunsResponse(BaseModel):
    runs: list[StoredBacktestRunResponse]


class StrategyVersionResponse(BaseModel):
    strategy_id: int
    name: str
    status: str
    medium_entry_threshold: int
    short_entry_threshold: int
    stop_loss_pct: float
    take_profit_pct: float
    max_holding_days: int
    position_size_pct: float
    created_at: str
    notes: str


class StrategyVersionsResponse(BaseModel):
    strategies: list[StrategyVersionResponse]


class EvolutionRunRequest(BaseModel):
    tickers: list[str]
    training_start_date: str
    training_end_date: str
    validation_start_date: str
    validation_end_date: str
    initial_cash: float = 10_000.0


class EvolutionRunResponse(BaseModel):
    candidate_strategy_id: int | None
    training_run_id: int | None
    validation_run_id: int | None
    active_validation_return: float
    validation_total_return: float
    max_drawdown: float
    message: str


class HistorySyncRequestModel(BaseModel):
    tickers: list[str]
    end_date: str | None = None


class HistorySyncTickerResponse(BaseModel):
    ticker: str
    source: str
    status: str
    bars_before: int
    bars_after: int
    bars_added: int
    latest_date: str | None
    message: str


class HistorySyncResponse(BaseModel):
    run_id: int
    tickers: list[HistorySyncTickerResponse]
    completed_count: int
    failed_count: int


class StoredHistorySyncRunResponse(BaseModel):
    run_id: int
    tickers: list[str]
    started_at: str
    completed_at: str | None
    completed_count: int
    failed_count: int


class HistorySyncRunsResponse(BaseModel):
    runs: list[StoredHistorySyncRunResponse]


class ScoreSnapshotResponse(BaseModel):
    ticker: str
    date: str
    source: str
    medium_term_score: int
    short_term_score: int
    action: str
    score: dict[str, Any]
    input_snapshot: dict[str, Any]
    created_at: str


class ScoreSnapshotsResponse(BaseModel):
    ticker: str
    snapshots: list[ScoreSnapshotResponse]
