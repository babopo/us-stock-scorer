from stock_scorer.backtesting import BacktestRequest, run_backtest
from stock_scorer.market_data import DailyBar
from stock_scorer.research_store import initialize_research_store, list_backtest_runs, open_research_connection, upsert_historical_bars


def test_run_backtest_persists_metrics_and_trades(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()
    bars = rising_bars("2026-01", count=80)
    with open_research_connection() as connection:
        upsert_historical_bars(connection, "MSFT", bars)

    summary = run_backtest(
        BacktestRequest(
            tickers=["MSFT"],
            start_date="2026-01-25",
            end_date="2026-03-15",
            initial_cash=10_000,
        )
    )

    with open_research_connection() as connection:
        runs = list_backtest_runs(connection)
        trade_count = connection.execute("select count(*) from backtest_trades where run_id = ?", (summary.run_id,)).fetchone()[0]

    assert summary.run_id > 0
    assert summary.metrics.trade_count >= 1
    assert summary.metrics.total_return > 0
    assert summary.metrics.buy_hold_return > 0
    assert runs[0].run_id == summary.run_id
    assert trade_count == summary.metrics.trade_count


def rising_bars(prefix: str, count: int) -> list[DailyBar]:
    bars = []
    for index in range(count):
        day = index + 1
        month = 1 + (day - 1) // 28
        date = f"{prefix[:5]}{month:02d}-{((day - 1) % 28) + 1:02d}"
        price = 100 + index
        bars.append(
            DailyBar(
                date=date,
                open=price - 0.5,
                high=price + 1,
                low=price - 1,
                close=price,
                adjusted_close=price,
                volume=1_000_000 + index,
            )
        )
    return bars

