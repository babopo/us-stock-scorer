from datetime import date, timedelta

import httpx
import pytest

from stock_scorer.live_scoring import build_score_from_market_snapshot
from stock_scorer.market_data import (
    AlphaVantageClient,
    DailyBar,
    FinnhubClient,
    FmpClient,
    MarketDataRateLimited,
    MarketSnapshot,
)


def test_alpha_vantage_client_parses_daily_adjusted_and_overview():
    requested_functions: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_functions.append(request.url.params["function"])
        if request.url.params["function"] == "TIME_SERIES_DAILY_ADJUSTED":
            return httpx.Response(
                200,
                json={
                    "Meta Data": {
                        "2. Symbol": "MSFT",
                        "3. Last Refreshed": "2026-05-20",
                    },
                    "Time Series (Daily)": {
                        "2026-05-20": {
                            "1. open": "450.00",
                            "2. high": "455.00",
                            "3. low": "448.00",
                            "4. close": "452.10",
                            "5. adjusted close": "452.10",
                            "6. volume": "30234567",
                            "7. dividend amount": "0.0000",
                            "8. split coefficient": "1.0",
                        },
                        "2026-05-19": {
                            "1. open": "445.00",
                            "2. high": "451.00",
                            "3. low": "443.50",
                            "4. close": "449.00",
                            "5. adjusted close": "449.00",
                            "6. volume": "25400000",
                            "7. dividend amount": "0.0000",
                            "8. split coefficient": "1.0",
                        },
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "Symbol": "MSFT",
                "Name": "Microsoft Corporation",
                "MarketCapitalization": "3350000000000",
                "PERatio": "34.5",
                "ForwardPE": "29.1",
                "ProfitMargin": "0.36",
                "QuarterlyRevenueGrowthYOY": "0.13",
                "QuarterlyEarningsGrowthYOY": "0.18",
                "Beta": "0.89",
            },
        )

    client = AlphaVantageClient(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    snapshot = client.fetch_snapshot("msft")

    assert requested_functions == ["TIME_SERIES_DAILY_ADJUSTED", "OVERVIEW"]
    assert snapshot.ticker == "MSFT"
    assert snapshot.company_name == "Microsoft Corporation"
    assert snapshot.last_price == 452.10
    assert snapshot.data_as_of == "2026-05-20"
    assert snapshot.daily_bars[0].adjusted_close == 452.10
    assert snapshot.overview["PERatio"] == "34.5"


def test_alpha_vantage_client_raises_rate_limited_for_note_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "Note": "Thank you for using Alpha Vantage! Our standard API rate limit is 25 requests per day."
            },
        )

    client = AlphaVantageClient(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(MarketDataRateLimited):
        client.fetch_snapshot("MSFT")


def test_fmp_client_parses_quote_history_profile_and_income_statement():
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        assert request.url.params["apikey"] == "test-key"
        if request.url.path == "/stable/quote":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "MSFT",
                        "name": "Microsoft Corporation",
                        "price": 452.1,
                    }
                ],
            )
        if request.url.path == "/stable/historical-price-eod/full":
            return httpx.Response(
                200,
                json=[
                    {
                        "date": "2026-05-20",
                        "open": 450.0,
                        "high": 455.0,
                        "low": 448.0,
                        "close": 452.1,
                        "adjClose": 452.1,
                        "volume": 30234567,
                    },
                    {
                        "date": "2026-05-19",
                        "open": 445.0,
                        "high": 451.0,
                        "low": 443.5,
                        "close": 449.0,
                        "adjClose": 449.0,
                        "volume": 25400000,
                    },
                ],
            )
        if request.url.path == "/stable/profile":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "MSFT",
                        "companyName": "Microsoft Corporation",
                        "mktCap": 3350000000000,
                        "pe": 34.5,
                        "beta": 0.89,
                    }
                ],
            )
        return httpx.Response(
            200,
            json=[
                {
                    "date": "2025-06-30",
                    "revenue": 245000000000,
                    "netIncome": 88100000000,
                    "eps": 11.8,
                },
                {
                    "date": "2024-06-30",
                    "revenue": 211000000000,
                    "netIncome": 72400000000,
                    "eps": 9.7,
                },
            ],
        )

    client = FmpClient(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    snapshot = client.fetch_snapshot("msft")

    assert requested_paths == [
        "/stable/quote",
        "/stable/historical-price-eod/full",
        "/stable/profile",
        "/stable/income-statement",
    ]
    assert snapshot.ticker == "MSFT"
    assert snapshot.company_name == "Microsoft Corporation"
    assert snapshot.last_price == 452.1
    assert snapshot.data_as_of == "2026-05-20"
    assert snapshot.source == "fmp"
    assert snapshot.daily_bars[0].adjusted_close == 452.1
    assert snapshot.overview["Name"] == "Microsoft Corporation"
    assert snapshot.overview["PERatio"] == 34.5
    assert snapshot.overview["ProfitMargin"] == pytest.approx(0.3595, rel=0.001)
    assert snapshot.overview["QuarterlyRevenueGrowthYOY"] == pytest.approx(0.1611, rel=0.001)


def test_fmp_client_raises_rate_limited_for_429():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"Error Message": "Too many requests"})

    client = FmpClient(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(MarketDataRateLimited):
        client.fetch_snapshot("MSFT")


def test_finnhub_client_parses_quote_candles_profile_and_metrics():
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        assert request.url.params["token"] == "test-key"
        if request.url.path == "/api/v1/quote":
            return httpx.Response(200, json={"c": 452.1, "t": 1779235200})
        if request.url.path == "/api/v1/stock/candle":
            return httpx.Response(
                200,
                json={
                    "s": "ok",
                    "t": [1779235200, 1779148800],
                    "o": [450.0, 445.0],
                    "h": [455.0, 451.0],
                    "l": [448.0, 443.5],
                    "c": [452.1, 449.0],
                    "v": [30234567, 25400000],
                },
            )
        if request.url.path == "/api/v1/stock/profile2":
            return httpx.Response(
                200,
                json={
                    "ticker": "MSFT",
                    "name": "Microsoft Corporation",
                    "marketCapitalization": 3350000,
                },
            )
        return httpx.Response(
            200,
            json={
                "metric": {
                    "peTTM": 34.5,
                    "beta": 0.89,
                    "netProfitMarginAnnual": 36.0,
                    "revenueGrowthTTMYoy": 13.0,
                    "epsGrowthTTMYoy": 18.0,
                }
            },
        )

    client = FinnhubClient(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    snapshot = client.fetch_snapshot("msft")

    assert requested_paths == [
        "/api/v1/quote",
        "/api/v1/stock/candle",
        "/api/v1/stock/profile2",
        "/api/v1/stock/metric",
    ]
    assert snapshot.ticker == "MSFT"
    assert snapshot.company_name == "Microsoft Corporation"
    assert snapshot.last_price == 452.1
    assert snapshot.data_as_of == "2026-05-20"
    assert snapshot.source == "finnhub"
    assert snapshot.daily_bars[0].adjusted_close == 452.1
    assert snapshot.overview["Name"] == "Microsoft Corporation"
    assert snapshot.overview["MarketCapitalization"] == 3_350_000_000_000
    assert snapshot.overview["PERatio"] == 34.5
    assert snapshot.overview["ProfitMargin"] == pytest.approx(0.36)
    assert snapshot.overview["QuarterlyRevenueGrowthYOY"] == pytest.approx(0.13)


def test_finnhub_client_raises_rate_limited_for_429():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "API limit reached"})

    client = FinnhubClient(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(MarketDataRateLimited):
        client.fetch_snapshot("MSFT")


def test_build_score_from_market_snapshot_uses_real_price_and_source():
    first_day = date(2026, 5, 20)
    bars = [
        DailyBar(
            date=(first_day - timedelta(days=index)).isoformat(),
            open=100 + (60 - index) * 0.3,
            high=101 + (60 - index) * 0.3,
            low=99 + (60 - index) * 0.3,
            close=100 + (60 - index) * 0.3,
            adjusted_close=100 + (60 - index) * 0.3,
            volume=25_000_000,
        )
        for index in range(60)
    ]
    snapshot = MarketSnapshot(
        ticker="MSFT",
        company_name="Microsoft Corporation",
        last_price=118.0,
        data_as_of="2026-05-20",
        daily_bars=bars,
        overview={
            "PERatio": "34.5",
            "ForwardPE": "29.1",
            "ProfitMargin": "0.36",
            "QuarterlyRevenueGrowthYOY": "0.13",
            "QuarterlyEarningsGrowthYOY": "0.18",
            "Beta": "0.89",
        },
        source="alpha_vantage",
    )

    score = build_score_from_market_snapshot(snapshot)

    assert score.ticker == "MSFT"
    assert score.company_name == "Microsoft Corporation"
    assert score.last_price == 118.0
    assert score.data_as_of == "2026-05-20"
    assert score.data_source == "alpha_vantage"
    assert len(score.factors) == 5
    assert score.decision.summary
