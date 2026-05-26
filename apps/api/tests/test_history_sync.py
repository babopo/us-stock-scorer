from stock_scorer.history_sync import HistorySyncRequest, sync_historical_data
from stock_scorer.market_data import DailyBar, MarketSnapshot
from stock_scorer.research_store import (
    get_historical_bars,
    initialize_research_store,
    list_history_sync_runs,
    open_research_connection,
    upsert_historical_bars,
)


def test_sync_historical_data_fetches_existing_ticker_and_persists_new_bars(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()
    with open_research_connection() as connection:
        upsert_historical_bars(connection, "MSFT", [_bar("2026-01-01", 100)])

    calls: list[tuple[str, str]] = []

    def fake_fetch(source: str, ticker: str) -> MarketSnapshot:
        calls.append((source, ticker))
        return MarketSnapshot(
            ticker=ticker,
            company_name=ticker,
            last_price=103,
            data_as_of="2026-01-04",
            daily_bars=[
                _bar("2026-01-04", 103),
                _bar("2026-01-03", 102),
                _bar("2026-01-02", 101),
                _bar("2026-01-01", 100),
            ],
            overview={},
            source=source,
        )

    summary = sync_historical_data(
        HistorySyncRequest(tickers=["MSFT"], end_date="2026-01-04"),
        fetch_snapshot=fake_fetch,
        configured_sources=lambda: ["fmp"],
    )

    with open_research_connection() as connection:
        bars = get_historical_bars(connection, "MSFT", None, "2026-01-04")
        runs = list_history_sync_runs(connection)

    assert calls == [("fmp", "MSFT")]
    assert summary.tickers[0].status == "completed"
    assert summary.tickers[0].bars_added == 3
    assert [bar.date for bar in bars] == ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    assert runs[0].run_id == summary.run_id
    assert runs[0].completed_count == 1


def test_sync_historical_data_records_failed_ticker_without_stopping_batch(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()

    def fake_fetch(source: str, ticker: str) -> MarketSnapshot:
        if ticker == "MSFT":
            return MarketSnapshot(
                ticker=ticker,
                company_name=ticker,
                last_price=101,
                data_as_of="2026-01-02",
                daily_bars=[_bar("2026-01-02", 101), _bar("2026-01-01", 100)],
                overview={},
                source=source,
            )
        raise RuntimeError("provider unavailable")

    summary = sync_historical_data(
        HistorySyncRequest(tickers=["MSFT", "BAD"], end_date="2026-01-02"),
        fetch_snapshot=fake_fetch,
        configured_sources=lambda: ["fmp", "finnhub"],
    )

    assert [result.status for result in summary.tickers] == ["completed", "failed"]
    assert summary.completed_count == 1
    assert summary.failed_count == 1
    assert "provider unavailable" in summary.tickers[1].message


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

