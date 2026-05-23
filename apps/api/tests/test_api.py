from fastapi.testclient import TestClient

from stock_scorer.fixtures import get_stock_score as get_fixture_stock_score
from stock_scorer.app import app
from stock_scorer.market_data import MarketDataRateLimited
from stock_scorer import score_service


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_local_admin_origin_gets_cors_headers():
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_stock_score_endpoint():
    response = client.get("/v1/stocks/MSFT/score")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "MSFT"
    assert payload["medium_term_score"] == 82
    assert payload["short_term_label"] == "wait_pullback"
    assert payload["decision"]["action"] == "wait"


def test_unknown_stock_score_endpoint_returns_404():
    response = client.get("/v1/stocks/UNKNOWN/score")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticker not found: UNKNOWN"


def test_stock_score_endpoint_returns_503_when_real_provider_is_missing_key(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCE", "alpha_vantage")
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)

    response = client.get("/v1/stocks/MSFT/score")

    assert response.status_code == 503
    assert "ALPHA_VANTAGE_API_KEY" in response.json()["detail"]


def test_stock_score_endpoint_returns_503_when_fmp_provider_is_missing_key(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCE", "fmp")
    monkeypatch.delenv("FMP_API_KEY", raising=False)

    response = client.get("/v1/stocks/MSFT/score")

    assert response.status_code == 503
    assert "FMP_API_KEY" in response.json()["detail"]


def test_admin_provider_status_hides_secret_values(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCE", "fmp")
    monkeypatch.setenv("FMP_API_KEY", "secret-fmp-key")
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)

    response = client.get("/v1/admin/providers/status")

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

    response = client.get("/v1/admin/providers/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_source"] == "fmp,finnhub,alpha_vantage"
    assert payload["providers"]["fmp"]["active"] is True
    assert payload["providers"]["finnhub"]["api_key_configured"] is True
    assert payload["providers"]["finnhub"]["active"] is True
    assert payload["providers"]["alpha_vantage"]["active"] is True
    assert "secret-finnhub-key" not in response.text


def test_score_endpoint_falls_back_to_finnhub_when_fmp_is_rate_limited(monkeypatch):
    def raise_fmp_rate_limit(ticker: str):
        raise MarketDataRateLimited("FMP rate limit exceeded")

    def get_finnhub_score(ticker: str):
        return get_fixture_stock_score(ticker).model_copy(update={"data_source": "finnhub"})

    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCES", "fmp,finnhub")
    monkeypatch.setenv("FMP_API_KEY", "secret-fmp-key")
    monkeypatch.setenv("FINNHUB_API_KEY", "secret-finnhub-key")
    monkeypatch.setattr(score_service, "get_fmp_stock_score", raise_fmp_rate_limit)
    monkeypatch.setattr(score_service, "get_finnhub_stock_score", get_finnhub_score, raising=False)

    response = client.get("/v1/stocks/MSFT/score")

    assert response.status_code == 200
    assert response.json()["data_source"] == "finnhub"


def test_admin_raw_data_returns_fixture_debug_payload(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCE", "fixture")

    response = client.get("/v1/admin/stocks/MSFT/raw-data")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "MSFT"
    assert payload["source"] == "fixture"
    assert payload["raw"]["company_name"] == "Microsoft Corporation"


def test_admin_refresh_ticker_reuses_score_pipeline(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCE", "fixture")

    response = client.post("/v1/admin/stocks/MSFT/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "MSFT"
    assert payload["status"] == "completed"
    assert payload["score"]["ticker"] == "MSFT"
