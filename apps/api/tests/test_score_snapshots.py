from stock_scorer.history_sync import HistorySyncRequest, sync_historical_data
from stock_scorer.market_data import DailyBar, MarketSnapshot
from stock_scorer.research_store import (
    get_score_snapshots,
    initialize_research_store,
    open_research_connection,
)


def test_history_sync_generates_historical_score_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()

    def fake_fetch(source: str, ticker: str) -> MarketSnapshot:
        bars = [_bar(f"2026-03-{day:02d}", 100 + day) for day in range(1, 61)]
        return MarketSnapshot(
            ticker=ticker,
            company_name="Microsoft Corporation",
            last_price=160,
            data_as_of="2026-03-60",
            daily_bars=sorted(bars, key=lambda bar: bar.date, reverse=True),
            overview={
                "ProfitMargin": "0.25",
                "ReturnOnEquityTTM": "0.28",
                "ForwardPE": "24",
                "QuarterlyRevenueGrowthYOY": "0.14",
                "QuarterlyEarningsGrowthYOY": "0.18",
                "DebtToEquity": "0.5",
                "InterestCoverage": "15",
            },
            source=source,
        )

    sync_historical_data(
        HistorySyncRequest(tickers=["MSFT"], end_date="2026-03-60"),
        fetch_snapshot=fake_fetch,
        configured_sources=lambda: ["fmp"],
    )

    with open_research_connection() as connection:
        snapshots = get_score_snapshots(connection, "MSFT")

    assert snapshots
    assert snapshots[-1].ticker == "MSFT"
    assert snapshots[-1].date == "2026-03-60"
    assert snapshots[-1].medium_term_score >= 0
    assert snapshots[-1].score["company_name"] == "Microsoft Corporation"
    assert snapshots[-1].source == "fmp"


def test_score_snapshot_generation_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()

    def fake_fetch(source: str, ticker: str) -> MarketSnapshot:
        bars = [_bar(f"2026-04-{day:02d}", 200 + day) for day in range(1, 56)]
        return MarketSnapshot(
            ticker=ticker,
            company_name=ticker,
            last_price=255,
            data_as_of="2026-04-55",
            daily_bars=sorted(bars, key=lambda bar: bar.date, reverse=True),
            overview={"ProfitMargin": "0.22", "ForwardPE": "25"},
            source=source,
        )

    request = HistorySyncRequest(tickers=["MSFT"], end_date="2026-04-55")
    sync_historical_data(request, fetch_snapshot=fake_fetch, configured_sources=lambda: ["fmp"])
    sync_historical_data(request, fetch_snapshot=fake_fetch, configured_sources=lambda: ["fmp"])

    with open_research_connection() as connection:
        snapshots = get_score_snapshots(connection, "MSFT")

    dates = [snapshot.date for snapshot in snapshots]
    assert len(dates) == len(set(dates))


def _bar(day: str, price: float) -> DailyBar:
    return DailyBar(
        date=day,
        open=price - 0.5,
        high=price + 1,
        low=price - 1,
        close=price,
        adjusted_close=price,
        volume=1_000_000,
    )

