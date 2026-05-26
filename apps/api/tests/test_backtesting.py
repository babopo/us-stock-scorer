from stock_scorer.backtesting import BacktestRequest, run_backtest
from stock_scorer.market_data import DailyBar
from stock_scorer.research_store import (
    initialize_research_store,
    list_backtest_runs,
    open_research_connection,
    upsert_historical_bars,
    upsert_score_snapshot,
)


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


def test_run_backtest_prefers_persisted_score_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()
    bars = rising_bars("2026-01", count=80)
    with open_research_connection() as connection:
        upsert_historical_bars(connection, "MSFT", bars)
        for bar in bars:
            upsert_score_snapshot(
                connection,
                ticker="MSFT",
                date=bar.date,
                source="test",
                score=_snapshot_score(bar.date, medium=30, short=30),
                input_snapshot={"source": "test"},
            )
        upsert_score_snapshot(
            connection,
            ticker="MSFT",
            date="2026-02-22",
            source="test",
            score=_snapshot_score("2026-02-22", medium=90, short=90),
            input_snapshot={"source": "test"},
        )

    def fail_if_recomputed(*args, **kwargs):
        raise AssertionError("backtest should use persisted score snapshots")

    monkeypatch.setattr("stock_scorer.backtesting.build_score_from_market_snapshot", fail_if_recomputed)

    summary = run_backtest(
        BacktestRequest(
            tickers=["MSFT"],
            start_date="2026-01-25",
            end_date="2026-03-15",
            initial_cash=10_000,
        )
    )

    assert summary.metrics.trade_count >= 1
    assert summary.trades[0].entry_date == "2026-02-22"


def test_run_backtest_uses_portfolio_cash_and_daily_equity_curve(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()
    msft_bars = rising_bars("2026-01", count=80)
    nvda_bars = [DailyBar(**{**bar.__dict__, "adjusted_close": bar.adjusted_close * 2, "close": bar.close * 2}) for bar in msft_bars]
    with open_research_connection() as connection:
        upsert_historical_bars(connection, "MSFT", msft_bars)
        upsert_historical_bars(connection, "NVDA", nvda_bars)
        for ticker in ("MSFT", "NVDA"):
            for bar in msft_bars:
                upsert_score_snapshot(
                    connection,
                    ticker=ticker,
                    date=bar.date,
                    source="test",
                    score=_snapshot_score(bar.date, medium=90, short=90),
                    input_snapshot={"source": "test"},
                )

    summary = run_backtest(
        BacktestRequest(
            tickers=["MSFT", "NVDA"],
            start_date="2026-02-20",
            end_date="2026-03-10",
            initial_cash=10_000,
            max_positions=2,
            position_size_pct=0.4,
            commission_bps=10,
            slippage_bps=10,
        )
    )

    assert summary.equity_curve
    assert summary.equity_curve[0].date == "2026-02-20"
    assert summary.equity_curve[-1].total_equity != 10_000
    assert min(point.cash for point in summary.equity_curve) < 10_000
    assert max(point.positions_value for point in summary.equity_curve) > 0
    assert {trade.ticker for trade in summary.trades} == {"MSFT", "NVDA"}


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


def _snapshot_score(day: str, medium: int, short: int) -> dict[str, object]:
    return {
        "ticker": "MSFT",
        "company_name": "Microsoft Corporation",
        "last_price": 100.0,
        "medium_term_score": medium,
        "medium_term_label": "positive" if medium >= 65 else "weak",
        "short_term_score": short,
        "short_term_label": "entry" if short >= 75 else "avoid",
        "factors": [],
        "decision": {
            "action": "buy_in_tranches" if short >= 75 else "avoid",
            "summary": "snapshot",
            "trigger_conditions": [],
            "invalidation_conditions": [],
            "risks": [],
        },
        "data_as_of": day,
        "data_source": "snapshot",
    }
