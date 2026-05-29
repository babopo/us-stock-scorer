import os
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html

from stock_scorer.admin_models import (
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestRunsResponse,
    EvolutionRunRequest,
    EvolutionRunResponse,
    HistorySyncRequestModel,
    HistorySyncResponse,
    HistorySyncRunsResponse,
    LatestAnalysisItemResponse,
    LatestAnalysisResponse,
    OperationRecommendationResponse,
    ProviderHealth,
    ProviderStatusResponse,
    RawTickerDataResponse,
    RefreshTickerResponse,
    ScoreSnapshotsResponse,
    StrategyVersionResponse,
    StrategyVersionsResponse,
)
from stock_scorer.auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminLogoutResponse,
    AdminSessionResponse,
    get_admin_session,
    login_admin,
    logout_admin,
    require_admin_access,
    require_read_access,
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
from stock_scorer.backtesting import BacktestRequest, run_backtest
from stock_scorer.history_sync import HistorySyncRequest, sync_historical_data
from stock_scorer.research_store import (
    archive_strategy_candidate,
    get_latest_score_snapshots,
    initialize_research_store,
    get_score_snapshots,
    list_backtest_runs,
    list_history_sync_runs,
    list_strategy_versions,
    open_research_connection,
    promote_strategy_candidate,
)
from stock_scorer.score_service import get_active_source_label, get_configured_data_sources, get_stock_score
from stock_scorer.strategy_evolution import EvolutionRequest, evolve_strategy


DEFAULT_RESEARCH_TICKERS = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD", "INTC"]

app = FastAPI(title="US Stock Scorer API", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
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


@app.get("/openapi.json", include_in_schema=False, dependencies=[Depends(require_admin_access)])
def openapi_schema() -> dict[str, object]:
    return app.openapi()


@app.get("/docs", include_in_schema=False, dependencies=[Depends(require_admin_access)])
def swagger_docs():
    return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} - Swagger UI")


@app.get("/redoc", include_in_schema=False, dependencies=[Depends(require_admin_access)])
def redoc_docs():
    return get_redoc_html(openapi_url="/openapi.json", title=f"{app.title} - ReDoc")


@app.post("/v1/admin/auth/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest) -> AdminLoginResponse:
    return login_admin(payload)


@app.get("/v1/admin/auth/session", response_model=AdminSessionResponse)
def admin_session(session: AdminSessionResponse = Depends(get_admin_session)) -> AdminSessionResponse:
    return session


@app.post("/v1/admin/auth/logout", response_model=AdminLogoutResponse)
def admin_logout(logout: AdminLogoutResponse = Depends(logout_admin)) -> AdminLogoutResponse:
    return logout


@app.get("/v1/stocks/{ticker}/score", response_model=StockScoreResponse, dependencies=[Depends(require_read_access)])
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


@app.get("/v1/admin/providers/status", response_model=ProviderStatusResponse, dependencies=[Depends(require_admin_access)])
def admin_provider_status() -> ProviderStatusResponse:
    active_source = get_active_source_label()
    active_sources = set(get_configured_data_sources())
    return ProviderStatusResponse(
        active_source=active_source,
        providers={
            "fixture": ProviderHealth(name="fixture", api_key_configured=True, active=bool(active_sources & {"fixture", "fixtures"})),
            "fmp": ProviderHealth(
                name="fmp",
                api_key_configured=bool(os.getenv("FMP_API_KEY")),
                active="fmp" in active_sources,
            ),
            "finnhub": ProviderHealth(
                name="finnhub",
                api_key_configured=bool(os.getenv("FINNHUB_API_KEY")),
                active="finnhub" in active_sources,
            ),
            "alpha_vantage": ProviderHealth(
                name="alpha_vantage",
                api_key_configured=bool(os.getenv("ALPHA_VANTAGE_API_KEY")),
                active="alpha_vantage" in active_sources,
            ),
        },
    )


@app.get("/v1/admin/stocks/{ticker}/raw-data", response_model=RawTickerDataResponse, dependencies=[Depends(require_admin_access)])
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


@app.get("/v1/admin/stocks/{ticker}/snapshots", response_model=ScoreSnapshotsResponse, dependencies=[Depends(require_admin_access)])
def admin_ticker_score_snapshots(ticker: str, date: str | None = None) -> ScoreSnapshotsResponse:
    normalized = ticker.upper()
    initialize_research_store()
    with open_research_connection() as connection:
        snapshots = get_score_snapshots(connection, normalized, date=date)
    return ScoreSnapshotsResponse(ticker=normalized, snapshots=[asdict(snapshot) for snapshot in snapshots])


@app.get(
    "/v1/admin/research/latest-analysis",
    response_model=LatestAnalysisResponse,
    dependencies=[Depends(require_admin_access)],
)
def admin_latest_analysis() -> LatestAnalysisResponse:
    initialize_research_store()
    with open_research_connection() as connection:
        snapshots = get_latest_score_snapshots(connection, DEFAULT_RESEARCH_TICKERS)
    return LatestAnalysisResponse(
        tickers=DEFAULT_RESEARCH_TICKERS,
        updated_after_market_close=True,
        items=[_latest_analysis_item(ticker, snapshots.get(ticker)) for ticker in DEFAULT_RESEARCH_TICKERS],
    )


@app.post("/v1/admin/stocks/{ticker}/refresh", response_model=RefreshTickerResponse, dependencies=[Depends(require_admin_access)])
def admin_refresh_ticker(ticker: str) -> RefreshTickerResponse:
    normalized = ticker.upper()
    return RefreshTickerResponse(ticker=normalized, status="completed", score=stock_score(normalized))


def _latest_analysis_item(ticker: str, snapshot: object | None) -> LatestAnalysisItemResponse:
    if snapshot is None:
        return LatestAnalysisItemResponse(
            ticker=ticker,
            status="missing",
            date=None,
            source=None,
            company_name=None,
            last_price=None,
            medium_term_score=None,
            short_term_score=None,
            decision_summary="等待盘后数据更新。",
            recommendation=OperationRecommendationResponse(
                action="wait_update",
                label="等待更新",
                reason="没有可用的盘后分析快照。",
            ),
            factors=[],
            risks=[],
            created_at=None,
        )

    score = snapshot.score
    decision = score.get("decision", {}) if isinstance(score.get("decision"), dict) else {}
    recommendation = _operation_recommendation(
        medium_score=int(snapshot.medium_term_score),
        short_score=int(snapshot.short_term_score),
        action=str(decision.get("action", snapshot.action)),
    )
    return LatestAnalysisItemResponse(
        ticker=snapshot.ticker,
        status="ready",
        date=snapshot.date,
        source=snapshot.source,
        company_name=_optional_string(score.get("company_name")),
        last_price=_optional_float(score.get("last_price")),
        medium_term_score=snapshot.medium_term_score,
        short_term_score=snapshot.short_term_score,
        decision_summary=str(decision.get("summary", "")),
        recommendation=recommendation,
        factors=[factor for factor in score.get("factors", []) if isinstance(factor, dict)],
        risks=[str(risk) for risk in decision.get("risks", [])] if isinstance(decision.get("risks"), list) else [],
        created_at=snapshot.created_at,
    )


def _operation_recommendation(medium_score: int, short_score: int, action: str) -> OperationRecommendationResponse:
    if action == "avoid" or medium_score < 45:
        return OperationRecommendationResponse(action="sell", label="抛售", reason="中期评分转弱或系统判定为回避。")
    if medium_score >= 80 and short_score >= 70:
        return OperationRecommendationResponse(action="add", label="加仓", reason="中期和短期评分都强，适合顺势提高仓位。")
    if medium_score >= 65 and short_score >= 55:
        return OperationRecommendationResponse(action="build_position", label="建仓", reason="中期评分达标，短期条件允许分批建仓。")
    return OperationRecommendationResponse(action="trim", label="减仓", reason="评分未达到进攻条件，优先降低仓位风险。")


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@app.get("/v1/admin/backtests/runs", response_model=BacktestRunsResponse, dependencies=[Depends(require_admin_access)])
def admin_list_backtest_runs() -> BacktestRunsResponse:
    initialize_research_store()
    with open_research_connection() as connection:
        runs = list_backtest_runs(connection)
    return BacktestRunsResponse(runs=[asdict(run) for run in runs])


@app.post("/v1/admin/backtests/runs", response_model=BacktestRunResponse, dependencies=[Depends(require_admin_access)])
def admin_run_backtest(payload: BacktestRunRequest) -> BacktestRunResponse:
    summary = run_backtest(
        BacktestRequest(
            tickers=payload.tickers,
            start_date=payload.start_date,
            end_date=payload.end_date,
            initial_cash=payload.initial_cash,
            max_positions=payload.max_positions,
            position_size_pct=payload.position_size_pct,
            commission_bps=payload.commission_bps,
            slippage_bps=payload.slippage_bps,
        )
    )
    return BacktestRunResponse(**asdict(summary))


@app.get("/v1/admin/strategies", response_model=StrategyVersionsResponse, dependencies=[Depends(require_admin_access)])
def admin_list_strategies() -> StrategyVersionsResponse:
    initialize_research_store()
    with open_research_connection() as connection:
        strategies = list_strategy_versions(connection)
    return StrategyVersionsResponse(strategies=[asdict(strategy) for strategy in strategies])


@app.post("/v1/admin/strategies/{strategy_id}/promote", response_model=StrategyVersionResponse, dependencies=[Depends(require_admin_access)])
def admin_promote_strategy(strategy_id: int) -> StrategyVersionResponse:
    initialize_research_store()
    with open_research_connection() as connection:
        try:
            strategy = promote_strategy_candidate(connection, strategy_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
    return StrategyVersionResponse(**asdict(strategy))


@app.post("/v1/admin/strategies/{strategy_id}/archive", response_model=StrategyVersionResponse, dependencies=[Depends(require_admin_access)])
def admin_archive_strategy(strategy_id: int) -> StrategyVersionResponse:
    initialize_research_store()
    with open_research_connection() as connection:
        try:
            strategy = archive_strategy_candidate(connection, strategy_id)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
    return StrategyVersionResponse(**asdict(strategy))


@app.post("/v1/admin/strategies/evolve", response_model=EvolutionRunResponse, dependencies=[Depends(require_admin_access)])
def admin_evolve_strategy(payload: EvolutionRunRequest) -> EvolutionRunResponse:
    result = evolve_strategy(
        EvolutionRequest(
            tickers=payload.tickers,
            training_start_date=payload.training_start_date,
            training_end_date=payload.training_end_date,
            validation_start_date=payload.validation_start_date,
            validation_end_date=payload.validation_end_date,
            initial_cash=payload.initial_cash,
        )
    )
    return EvolutionRunResponse(**result.__dict__)


@app.get("/v1/admin/history/syncs", response_model=HistorySyncRunsResponse, dependencies=[Depends(require_admin_access)])
def admin_list_history_syncs() -> HistorySyncRunsResponse:
    initialize_research_store()
    with open_research_connection() as connection:
        runs = list_history_sync_runs(connection)
    return HistorySyncRunsResponse(runs=[asdict(run) for run in runs])


@app.post("/v1/admin/history/sync", response_model=HistorySyncResponse, dependencies=[Depends(require_admin_access)])
def admin_sync_history(payload: HistorySyncRequestModel) -> HistorySyncResponse:
    result = sync_historical_data(HistorySyncRequest(tickers=payload.tickers, end_date=payload.end_date))
    return HistorySyncResponse(**asdict(result))
