from fastapi.testclient import TestClient

from stock_scorer.app import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
