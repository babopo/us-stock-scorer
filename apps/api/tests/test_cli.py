from stock_scorer.cli import main
from stock_scorer.market_data import DailyBar
from stock_scorer.research_store import initialize_research_store, open_research_connection, upsert_historical_bars


def test_cli_runs_backtest_and_prints_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()
    with open_research_connection() as connection:
        upsert_historical_bars(connection, "MSFT", _cli_bars())

    exit_code = main(
        [
            "backtest",
            "run",
            "--tickers",
            "MSFT",
            "--start-date",
            "2026-01-25",
            "--end-date",
            "2026-03-15",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"run_id":' in output
    assert '"trade_count":' in output


def _cli_bars() -> list[DailyBar]:
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
