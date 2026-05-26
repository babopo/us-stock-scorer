from stock_scorer.market_data import DailyBar
from stock_scorer.research_store import (
    default_db_path,
    get_active_strategy,
    initialize_research_store,
    list_strategy_versions,
    open_research_connection,
    upsert_historical_bars,
)


def test_initialize_research_store_is_idempotent_and_seeds_active_strategy(tmp_path, monkeypatch):
    db_path = tmp_path / "research.sqlite3"
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(db_path))

    initialize_research_store()
    initialize_research_store()

    with open_research_connection() as connection:
        strategies = list_strategy_versions(connection)

    assert default_db_path() == db_path
    assert len(strategies) == 1
    assert strategies[0].status == "active"
    assert strategies[0].medium_entry_threshold == 65
    assert strategies[0].short_entry_threshold == 60


def test_historical_bars_round_trip_by_ticker_and_date(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()
    bars = [
        DailyBar(date="2026-01-03", open=12, high=13, low=11, close=12, adjusted_close=12, volume=1200),
        DailyBar(date="2026-01-01", open=10, high=11, low=9, close=10, adjusted_close=10, volume=1000),
        DailyBar(date="2026-01-02", open=11, high=12, low=10, close=11, adjusted_close=11, volume=1100),
    ]

    with open_research_connection() as connection:
        strategy = get_active_strategy(connection)
        upsert_historical_bars(connection, "MSFT", bars)
        stored = list(connection.execute("select count(*) from strategy_versions"))
        selected = [
            tuple(row)
            for row in connection.execute(
                "select date, adjusted_close from historical_bars where ticker = ? order by date",
                ("MSFT",),
            )
        ]

    assert strategy.status == "active"
    assert stored[0][0] == 1
    assert selected == [("2026-01-01", 10.0), ("2026-01-02", 11.0), ("2026-01-03", 12.0)]
