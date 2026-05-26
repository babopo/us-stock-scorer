from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from stock_scorer.market_data import MarketSnapshot
from stock_scorer.research_store import (
    complete_history_sync_run,
    count_historical_bars,
    initialize_research_store,
    insert_history_sync_result,
    insert_history_sync_run,
    latest_historical_bar_date,
    open_research_connection,
    upsert_historical_bars,
)
from stock_scorer.score_snapshots import generate_score_snapshots
from stock_scorer.score_service import fetch_market_snapshot_from_source, get_configured_data_sources


FetchSnapshot = Callable[[str, str], MarketSnapshot]
ConfiguredSources = Callable[[], list[str]]


@dataclass(frozen=True)
class HistorySyncRequest:
    tickers: list[str]
    end_date: str | None = None


@dataclass(frozen=True)
class HistorySyncTickerResult:
    ticker: str
    source: str
    status: str
    bars_before: int
    bars_after: int
    bars_added: int
    latest_date: str | None
    message: str


@dataclass(frozen=True)
class HistorySyncSummary:
    run_id: int
    tickers: list[HistorySyncTickerResult]
    completed_count: int
    failed_count: int


def sync_historical_data(
    request: HistorySyncRequest,
    *,
    fetch_snapshot: FetchSnapshot = fetch_market_snapshot_from_source,
    configured_sources: ConfiguredSources = get_configured_data_sources,
) -> HistorySyncSummary:
    initialize_research_store()
    tickers = [ticker.strip().upper() for ticker in request.tickers if ticker.strip()]
    end_date = request.end_date or date.today().isoformat()
    results: list[HistorySyncTickerResult] = []

    with open_research_connection() as connection:
        run_id = insert_history_sync_run(connection, tickers)
        for ticker in tickers:
            result = _sync_one_ticker(
                connection=connection,
                ticker=ticker,
                end_date=end_date,
                fetch_snapshot=fetch_snapshot,
                configured_sources=configured_sources,
            )
            results.append(result)
            insert_history_sync_result(connection, run_id=run_id, **result.__dict__)
        complete_history_sync_run(connection, run_id)

    return HistorySyncSummary(
        run_id=run_id,
        tickers=results,
        completed_count=sum(1 for result in results if result.status == "completed"),
        failed_count=sum(1 for result in results if result.status == "failed"),
    )


def _sync_one_ticker(
    *,
    connection: object,
    ticker: str,
    end_date: str,
    fetch_snapshot: FetchSnapshot,
    configured_sources: ConfiguredSources,
) -> HistorySyncTickerResult:
    bars_before = count_historical_bars(connection, ticker, end_date)
    errors: list[str] = []
    for source in configured_sources():
        if source in {"fixture", "fixtures"}:
            continue
        try:
            snapshot = fetch_snapshot(source, ticker)
        except Exception as exc:
            errors.append(f"{source}: {exc}")
            continue

        bars = [bar for bar in snapshot.daily_bars if bar.date <= end_date]
        if not bars:
            errors.append(f"{source}: no bars on or before {end_date}")
            continue

        upsert_historical_bars(connection, ticker, bars)
        generate_score_snapshots(
            connection,
            ticker=ticker,
            source=source,
            overview=snapshot.overview,
            company_name=snapshot.company_name,
            end_date=end_date,
        )
        bars_after = count_historical_bars(connection, ticker, end_date)
        latest_date = latest_historical_bar_date(connection, ticker)
        return HistorySyncTickerResult(
            ticker=ticker,
            source=source,
            status="completed",
            bars_before=bars_before,
            bars_after=bars_after,
            bars_added=max(0, bars_after - bars_before),
            latest_date=latest_date,
            message=f"Synced {len(bars)} bars from {source}.",
        )

    latest_date = latest_historical_bar_date(connection, ticker)
    return HistorySyncTickerResult(
        ticker=ticker,
        source=",".join(configured_sources()),
        status="failed",
        bars_before=bars_before,
        bars_after=bars_before,
        bars_added=0,
        latest_date=latest_date,
        message="; ".join(errors) or "No live historical data source configured.",
    )
