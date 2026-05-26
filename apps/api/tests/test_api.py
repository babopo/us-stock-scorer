from datetime import date, timedelta

from fastapi.testclient import TestClient

from stock_scorer.app import app
from stock_scorer.market_data import DailyBar, MarketDataRateLimited, MarketSnapshot
from stock_scorer.research_store import initialize_research_store, open_research_connection, upsert_historical_bars
from stock_scorer import score_service


client = TestClient(app)


def read_auth_headers(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_READ_TOKEN", "read-token")
    return {"Authorization": "Bearer read-token"}


def admin_static_auth_headers(monkeypatch):
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-static-token")
    return {"Authorization": "Bearer admin-static-token"}


def market_snapshot(source: str, overview: dict[str, object], last_price: float = 100.0) -> MarketSnapshot:
    first_day = date(2026, 5, 20)
    bars = [
        DailyBar(
            date=(first_day - timedelta(days=index)).isoformat(),
            open=100.0 - index,
            high=101.0 - index,
            low=99.0 - index,
            close=100.0 - index,
            adjusted_close=100.0 - index,
            volume=1_000_000,
        )
        for index in range(60)
    ]
    return MarketSnapshot(
        ticker="MSFT",
        company_name=f"{source} Microsoft",
        last_price=last_price,
        data_as_of="2026-05-20",
        daily_bars=bars,
        overview=overview,
        source=source,
    )


class FakeSnapshotClient:
    def __init__(self, source: str, snapshot: MarketSnapshot | Exception, calls: list[str]):
        self._source = source
        self._snapshot = snapshot
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    def fetch_snapshot(self, ticker: str) -> MarketSnapshot:
        self._calls.append(self._source)
        if isinstance(self._snapshot, Exception):
            raise self._snapshot
        return self._snapshot


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_local_admin_origin_gets_cors_headers():
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_stock_score_requires_bearer_token_when_read_token_is_configured(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_READ_TOKEN", "read-token")

    response = client.get("/v1/stocks/MSFT/score")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authorization bearer token is required"


def test_stock_score_endpoint_accepts_read_token(monkeypatch):
    response = client.get("/v1/stocks/MSFT/score", headers=read_auth_headers(monkeypatch))

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "MSFT"
    assert payload["medium_term_score"] == 82
    assert payload["short_term_label"] == "wait_pullback"
    assert payload["decision"]["action"] == "wait"


def test_stock_score_endpoint_accepts_default_local_read_token(monkeypatch):
    monkeypatch.delenv("STOCK_SCORER_READ_TOKEN", raising=False)

    response = client.get("/v1/stocks/MSFT/score", headers={"Authorization": "Bearer local-read-token"})

    assert response.status_code == 200
    assert response.json()["ticker"] == "MSFT"


def test_unknown_stock_score_endpoint_returns_404(monkeypatch):
    response = client.get("/v1/stocks/UNKNOWN/score", headers=read_auth_headers(monkeypatch))

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticker not found: UNKNOWN"


def test_stock_score_endpoint_returns_503_when_real_provider_is_missing_key(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCE", "alpha_vantage")
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)

    response = client.get("/v1/stocks/MSFT/score", headers=read_auth_headers(monkeypatch))

    assert response.status_code == 503
    assert "ALPHA_VANTAGE_API_KEY" in response.json()["detail"]


def test_stock_score_endpoint_returns_503_when_fmp_provider_is_missing_key(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCE", "fmp")
    monkeypatch.delenv("FMP_API_KEY", raising=False)

    response = client.get("/v1/stocks/MSFT/score", headers=read_auth_headers(monkeypatch))

    assert response.status_code == 503
    assert "FMP_API_KEY" in response.json()["detail"]


def test_stock_score_rejects_invalid_token_when_read_token_env_is_missing(monkeypatch):
    monkeypatch.delenv("STOCK_SCORER_READ_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    response = client.get("/v1/stocks/MSFT/score", headers={"Authorization": "Bearer any-token"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid bearer token"


def test_admin_provider_status_rejects_read_token(monkeypatch):
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-static-token")
    response = client.get("/v1/admin/providers/status", headers=read_auth_headers(monkeypatch))

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin authorization is required"


def test_admin_login_returns_session_token(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret-password")

    response = client.post(
        "/v1/admin/auth/login",
        json={"username": "admin", "password": "secret-password"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in_seconds"] > 0
    assert isinstance(payload["access_token"], str)
    assert payload["access_token"]


def test_admin_login_rejects_invalid_credentials(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret-password")

    response = client.post(
        "/v1/admin/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid admin credentials"


def test_admin_session_token_allows_admin_and_score_requests(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret-password")

    login_response = client.post(
        "/v1/admin/auth/login",
        json={"username": "admin", "password": "secret-password"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    status_response = client.get("/v1/admin/providers/status", headers=headers)
    score_response = client.get("/v1/stocks/MSFT/score", headers=headers)
    session_response = client.get("/v1/admin/auth/session", headers=headers)

    assert status_response.status_code == 200
    assert score_response.status_code == 200
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is True
    assert session_response.json()["role"] == "admin"


def test_admin_logout_invalidates_session_token(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret-password")

    login_response = client.post(
        "/v1/admin/auth/login",
        json={"username": "admin", "password": "secret-password"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout_response = client.post("/v1/admin/auth/logout", headers=headers)
    status_response = client.get("/v1/admin/providers/status", headers=headers)

    assert logout_response.status_code == 200
    assert logout_response.json() == {"status": "logged_out"}
    assert status_response.status_code == 401


def test_admin_provider_status_hides_secret_values(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCE", "fmp")
    monkeypatch.setenv("FMP_API_KEY", "secret-fmp-key")
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)

    response = client.get("/v1/admin/providers/status", headers=admin_static_auth_headers(monkeypatch))

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_source"] == "fmp"
    assert payload["providers"]["fmp"]["api_key_configured"] is True
    assert payload["providers"]["alpha_vantage"]["api_key_configured"] is False
    assert "secret-fmp-key" not in response.text


def test_admin_provider_status_includes_finnhub_fallback(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCES", "fmp,finnhub,alpha_vantage")
    monkeypatch.setenv("FMP_API_KEY", "secret-fmp-key")
    monkeypatch.setenv("FINNHUB_API_KEY", "secret-finnhub-key")
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)

    response = client.get("/v1/admin/providers/status", headers=admin_static_auth_headers(monkeypatch))

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_source"] == "fmp,finnhub,alpha_vantage"
    assert payload["providers"]["fmp"]["active"] is True
    assert payload["providers"]["finnhub"]["api_key_configured"] is True
    assert payload["providers"]["finnhub"]["active"] is True
    assert payload["providers"]["alpha_vantage"]["active"] is True
    assert "secret-finnhub-key" not in response.text


def test_admin_backtest_routes_require_admin_and_return_run_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()
    with open_research_connection() as connection:
        upsert_historical_bars(connection, "MSFT", _api_backtest_bars())

    admin_headers = admin_static_auth_headers(monkeypatch)
    rejected = client.get("/v1/admin/backtests/runs", headers=read_auth_headers(monkeypatch))
    response = client.post(
        "/v1/admin/backtests/runs",
        headers=admin_headers,
        json={"tickers": ["MSFT"], "start_date": "2026-01-25", "end_date": "2026-03-15", "initial_cash": 10000},
    )
    list_response = client.get("/v1/admin/backtests/runs", headers=admin_headers)

    assert rejected.status_code == 403
    assert response.status_code == 200
    assert response.json()["metrics"]["trade_count"] >= 1
    assert list_response.status_code == 200
    assert list_response.json()["runs"][0]["run_id"] == response.json()["run_id"]


def test_admin_strategy_routes_return_versions_and_evolution_candidate(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()
    with open_research_connection() as connection:
        upsert_historical_bars(connection, "MSFT", _api_backtest_bars())

    versions_response = client.get("/v1/admin/strategies", headers=admin_static_auth_headers(monkeypatch))
    evolution_response = client.post(
        "/v1/admin/strategies/evolve",
        headers=admin_static_auth_headers(monkeypatch),
        json={
            "tickers": ["MSFT"],
            "training_start_date": "2026-01-25",
            "training_end_date": "2026-02-20",
            "validation_start_date": "2026-02-21",
            "validation_end_date": "2026-03-20",
            "initial_cash": 10000,
        },
    )

    assert versions_response.status_code == 200
    assert versions_response.json()["strategies"][0]["status"] == "active"
    assert evolution_response.status_code == 200
    assert evolution_response.json()["candidate_strategy_id"] is not None


def _api_backtest_bars() -> list[DailyBar]:
    bars = []
    for index in range(90):
        month = 1 + index // 30
        day = index % 30 + 1
        price = 100 + index
        bars.append(
            DailyBar(
                date=f"2026-{month:02d}-{day:02d}",
                open=price - 0.5,
                high=price + 1,
                low=price - 1,
                close=price,
                adjusted_close=price,
                volume=1_000_000 + index,
            )
        )
    return bars


def test_score_endpoint_falls_back_to_finnhub_when_fmp_is_rate_limited(monkeypatch):
    def fetch_by_source(source: str, ticker: str):
        if source == "fmp":
            raise MarketDataRateLimited("FMP rate limit exceeded")
        if source == "finnhub":
            return market_snapshot(
                "finnhub",
                {
                    "PERatio": "28.5",
                    "ProfitMargin": "0.25",
                    "MarketCapitalization": "2500000000000",
                },
            )
        raise AssertionError(source)

    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCES", "fmp,finnhub")
    monkeypatch.setenv("FMP_API_KEY", "secret-fmp-key")
    monkeypatch.setenv("FINNHUB_API_KEY", "secret-finnhub-key")
    monkeypatch.setattr(score_service, "fetch_market_snapshot_from_source", fetch_by_source)

    response = client.get("/v1/stocks/MSFT/score", headers=read_auth_headers(monkeypatch))

    assert response.status_code == 200
    assert response.json()["data_source"] == "finnhub"


def test_score_endpoint_fills_missing_primary_fields_from_later_sources(monkeypatch):
    calls: list[str] = []
    fmp_snapshot = market_snapshot(
        "fmp",
        {
            "PERatio": None,
            "ForwardPE": "",
            "ProfitMargin": "0.25",
            "MarketCapitalization": "2500000000000",
        },
        last_price=321.0,
    )
    finnhub_snapshot = market_snapshot(
        "finnhub",
        {
            "PERatio": "28.5",
            "ForwardPE": "24.2",
            "Beta": "0.92",
        },
        last_price=999.0,
    )

    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCES", "fmp,finnhub")
    monkeypatch.setenv("FMP_API_KEY", "secret-fmp-key")
    monkeypatch.setenv("FINNHUB_API_KEY", "secret-finnhub-key")
    monkeypatch.setattr(
        score_service,
        "FmpClient",
        lambda *args, **kwargs: FakeSnapshotClient("fmp", fmp_snapshot, calls),
    )
    monkeypatch.setattr(
        score_service,
        "FinnhubClient",
        lambda *args, **kwargs: FakeSnapshotClient("finnhub", finnhub_snapshot, calls),
    )

    response = client.get("/v1/stocks/MSFT/score", headers=read_auth_headers(monkeypatch))

    assert response.status_code == 200
    payload = response.json()
    assert calls == ["fmp", "finnhub"]
    assert payload["last_price"] == 321.0
    assert payload["data_source"] == "fmp+finnhub"
    valuation = next(factor for factor in payload["factors"] if factor["name"] == "估值")
    assert valuation["score"] > 50
    assert "PE/Forward PE 约 24.2" in valuation["evidence"][0]


def test_score_endpoint_ignores_later_provider_failure_when_primary_succeeds(monkeypatch):
    calls: list[str] = []
    fmp_snapshot = market_snapshot(
        "fmp",
        {
            "PERatio": "20",
            "ProfitMargin": "0.25",
            "MarketCapitalization": "2500000000000",
        },
        last_price=321.0,
    )

    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCES", "fmp,finnhub")
    monkeypatch.setenv("FMP_API_KEY", "secret-fmp-key")
    monkeypatch.setenv("FINNHUB_API_KEY", "secret-finnhub-key")
    monkeypatch.setattr(
        score_service,
        "FmpClient",
        lambda *args, **kwargs: FakeSnapshotClient("fmp", fmp_snapshot, calls),
    )
    monkeypatch.setattr(
        score_service,
        "FinnhubClient",
        lambda *args, **kwargs: FakeSnapshotClient(
            "finnhub",
            MarketDataRateLimited("Finnhub rate limit exceeded"),
            calls,
        ),
    )

    response = client.get("/v1/stocks/MSFT/score", headers=read_auth_headers(monkeypatch))

    assert response.status_code == 200
    assert response.json()["data_source"] == "fmp"
    assert calls == ["fmp", "finnhub"]


def test_admin_raw_data_returns_fixture_debug_payload(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCE", "fixture")

    response = client.get("/v1/admin/stocks/MSFT/raw-data", headers=admin_static_auth_headers(monkeypatch))

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "MSFT"
    assert payload["source"] == "fixture"
    assert payload["raw"]["company_name"] == "Microsoft Corporation"


def test_admin_refresh_ticker_reuses_score_pipeline(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCE", "fixture")

    response = client.post("/v1/admin/stocks/MSFT/refresh", headers=admin_static_auth_headers(monkeypatch))

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "MSFT"
    assert payload["status"] == "completed"
    assert payload["score"]["ticker"] == "MSFT"
