from stock_scorer.market_data import DailyBar
from stock_scorer.research_store import initialize_research_store, list_strategy_versions, open_research_connection, upsert_historical_bars
from stock_scorer.strategy_evolution import EvolutionRequest, evolve_strategy


def test_evolve_strategy_stores_candidate_version(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_SCORER_DB_PATH", str(tmp_path / "research.sqlite3"))
    initialize_research_store()
    with open_research_connection() as connection:
        upsert_historical_bars(connection, "MSFT", mixed_trend_bars())

    result = evolve_strategy(
        EvolutionRequest(
            tickers=["MSFT"],
            training_start_date="2026-01-25",
            training_end_date="2026-02-20",
            validation_start_date="2026-02-21",
            validation_end_date="2026-03-20",
            initial_cash=10_000,
        )
    )

    with open_research_connection() as connection:
        versions = list_strategy_versions(connection)

    assert result.candidate_strategy_id is not None
    assert result.validation_total_return >= result.active_validation_return
    assert any(version.status == "candidate" for version in versions)


def mixed_trend_bars() -> list[DailyBar]:
    bars = []
    for index in range(90):
        month = 1 + index // 30
        day = index % 30 + 1
        price = 100 + index * 0.9
        if 45 <= index <= 52:
            price -= 8
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

