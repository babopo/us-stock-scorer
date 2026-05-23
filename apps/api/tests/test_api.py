from fastapi.testclient import TestClient

from stock_scorer.fixtures import get_stock_score as get_fixture_stock_score
from stock_scorer.app import app
from stock_scorer.market_data import MarketDataRateLimited
from stock_scorer import score_service


client = TestClient(app)


def read_auth_headers(monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_READ_TOKEN", "read-token")
    return {"Authorization": "Bearer read-token"}


def admin_static_auth_headers(monkeypatch):
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "admin-static-token")
    return {"Authorization": "Bearer admin-static-token"}


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


def test_stock_score_endpoint_accepts_default_wxlogin_read_token(monkeypatch):
    monkeypatch.delenv("STOCK_SCORER_READ_TOKEN", raising=False)

    response = client.get("/v1/stocks/MSFT/score", headers={"Authorization": "Bearer wxlogin"})

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

    response = client.get("/v1/stocks/MSFT/score", headers=read_auth_headers(monkeypatch))

    assert response.status_code == 200
    assert response.json()["data_source"] == "finnhub"


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
