from fastapi.testclient import TestClient

from stock_scorer.app import app


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
