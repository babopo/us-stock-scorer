from stock_scorer.market_data import DailyBar
from stock_scorer.research_store import (
    archive_strategy_candidate,
    default_db_path,
    get_active_strategy,
    initialize_research_store,
    insert_strategy_version,
    list_strategy_versions,
    open_research_connection,
    promote_strategy_candidate,
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


def test_promote_strategy_candidate_archives_previous_active(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()
    with open_research_connection() as connection:
        previous_active = get_active_strategy(connection)
        candidate = insert_strategy_version(
            connection,
            name="candidate-v2",
            status="candidate",
            medium_entry_threshold=60,
            short_entry_threshold=55,
            stop_loss_pct=0.07,
            take_profit_pct=0.22,
            max_holding_days=18,
            position_size_pct=0.5,
            notes="review candidate",
        )

        promoted = promote_strategy_candidate(connection, candidate.strategy_id)
        strategies = list_strategy_versions(connection)

    assert promoted.status == "active"
    assert promoted.strategy_id == candidate.strategy_id
    assert [strategy.status for strategy in strategies if strategy.strategy_id == previous_active.strategy_id] == ["archived"]
    assert len([strategy for strategy in strategies if strategy.status == "active"]) == 1


def test_archive_strategy_candidate_rejects_active_strategy(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()
    with open_research_connection() as connection:
        active = get_active_strategy(connection)
        candidate = insert_strategy_version(
            connection,
            name="candidate-v2",
            status="candidate",
            medium_entry_threshold=60,
            short_entry_threshold=55,
            stop_loss_pct=0.07,
            take_profit_pct=0.22,
            max_holding_days=18,
            position_size_pct=0.5,
            notes="review candidate",
        )

        archived = archive_strategy_candidate(connection, candidate.strategy_id)

        try:
            archive_strategy_candidate(connection, active.strategy_id)
        except ValueError as error:
            message = str(error)
        else:
            message = ""

    assert archived.status == "archived"
    assert "Only candidate strategies can be archived" in message
