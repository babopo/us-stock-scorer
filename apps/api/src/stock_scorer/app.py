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
    ProviderHealth,
    ProviderStatusResponse,
    RawTickerDataResponse,
    RefreshTickerResponse,
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
from stock_scorer.research_store import initialize_research_store, list_backtest_runs, list_strategy_versions, open_research_connection
from stock_scorer.score_service import get_active_source_label, get_configured_data_sources, get_stock_score
from stock_scorer.strategy_evolution import EvolutionRequest, evolve_strategy


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


@app.post("/v1/admin/stocks/{ticker}/refresh", response_model=RefreshTickerResponse, dependencies=[Depends(require_admin_access)])
def admin_refresh_ticker(ticker: str) -> RefreshTickerResponse:
    normalized = ticker.upper()
    return RefreshTickerResponse(ticker=normalized, status="completed", score=stock_score(normalized))


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
        )
    )
    return BacktestRunResponse(**asdict(summary))


@app.get("/v1/admin/strategies", response_model=StrategyVersionsResponse, dependencies=[Depends(require_admin_access)])
def admin_list_strategies() -> StrategyVersionsResponse:
    initialize_research_store()
    with open_research_connection() as connection:
        strategies = list_strategy_versions(connection)
    return StrategyVersionsResponse(strategies=[asdict(strategy) for strategy in strategies])


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
