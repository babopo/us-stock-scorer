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


def test_cli_runs_history_sync_with_default_end_date(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))

    from stock_scorer import cli

    monkeypatch.setattr(
        cli,
        "sync_historical_data",
        lambda request: {"tickers": request.tickers, "end_date": request.end_date},
    )

    exit_code = cli.main(["history", "sync", "--tickers", "MSFT,NVDA"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"MSFT"' in output
    assert '"NVDA"' in output


def test_cli_loads_local_env_file_without_overwriting_existing_values(tmp_path, monkeypatch):
    from stock_scorer.cli import load_local_env_file

    env_file = tmp_path / ".env"
    env_file.write_text("STOCK_SCORER_DATA_SOURCES=fmp,finnhub\nEXISTING_VALUE=from-file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("STOCK_SCORER_DATA_SOURCES", raising=False)
    monkeypatch.setenv("EXISTING_VALUE", "from-env")

    load_local_env_file()

    assert __import__("os").environ["STOCK_SCORER_DATA_SOURCES"] == "fmp,finnhub"
    assert __import__("os").environ["EXISTING_VALUE"] == "from-env"


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
