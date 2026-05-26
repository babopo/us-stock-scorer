import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stock_scorer.market_data import DailyBar


DEFAULT_DB_PATH = Path(__file__).resolve().parents[4] / "apps" / "api" / "data" / "stock_scorer.sqlite3"


@dataclass(frozen=True)
class StrategyVersion:
    strategy_id: int
    name: str
    status: str
    medium_entry_threshold: int
    short_entry_threshold: int
    stop_loss_pct: float
    take_profit_pct: float
    max_holding_days: int
    position_size_pct: float
    created_at: str
    notes: str


@dataclass(frozen=True)
class StoredBacktestRun:
    run_id: int
    strategy_id: int
    tickers: list[str]
    start_date: str
    end_date: str
    initial_cash: float
    created_at: str
    total_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    buy_hold_return: float


def default_db_path() -> Path:
    return Path(os.getenv("STOCK_SCORER_DB_PATH", str(DEFAULT_DB_PATH))).expanduser()


def open_research_connection(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("pragma foreign_keys = on")
    return connection


def initialize_research_store(path: Path | None = None) -> None:
    with open_research_connection(path) as connection:
        connection.executescript(
            """
            create table if not exists strategy_versions (
                id integer primary key autoincrement,
                name text not null,
                status text not null check (status in ('active', 'candidate', 'archived')),
                medium_entry_threshold integer not null,
                short_entry_threshold integer not null,
                stop_loss_pct real not null,
                take_profit_pct real not null,
                max_holding_days integer not null,
                position_size_pct real not null,
                created_at text not null default (datetime('now')),
                notes text not null default ''
            );

            create unique index if not exists one_active_strategy
            on strategy_versions(status)
            where status = 'active';

            create table if not exists historical_bars (
                ticker text not null,
                date text not null,
                open real not null,
                high real not null,
                low real not null,
                close real not null,
                adjusted_close real not null,
                volume integer not null,
                primary key (ticker, date)
            );

            create table if not exists backtest_runs (
                id integer primary key autoincrement,
                strategy_id integer not null references strategy_versions(id),
                tickers text not null,
                start_date text not null,
                end_date text not null,
                initial_cash real not null,
                created_at text not null default (datetime('now'))
            );

            create table if not exists backtest_trades (
                id integer primary key autoincrement,
                run_id integer not null references backtest_runs(id) on delete cascade,
                ticker text not null,
                entry_date text not null,
                exit_date text not null,
                entry_price real not null,
                exit_price real not null,
                shares real not null,
                return_pct real not null,
                holding_days integer not null,
                exit_reason text not null
            );

            create table if not exists backtest_metrics (
                run_id integer primary key references backtest_runs(id) on delete cascade,
                total_return real not null,
                annualized_return real not null,
                max_drawdown real not null,
                win_rate real not null,
                trade_count integer not null,
                average_holding_days real not null,
                buy_hold_return real not null
            );

            create table if not exists evolution_candidates (
                id integer primary key autoincrement,
                strategy_id integer not null references strategy_versions(id),
                training_run_id integer not null references backtest_runs(id),
                validation_run_id integer not null references backtest_runs(id),
                active_validation_return real not null,
                candidate_validation_return real not null,
                max_drawdown real not null,
                created_at text not null default (datetime('now'))
            );
            """
        )
        if connection.execute("select count(*) from strategy_versions").fetchone()[0] == 0:
            connection.execute(
                """
                insert into strategy_versions (
                    name, status, medium_entry_threshold, short_entry_threshold,
                    stop_loss_pct, take_profit_pct, max_holding_days, position_size_pct, notes
                )
                values (?, 'active', ?, ?, ?, ?, ?, ?, ?)
                """,
                ("default-v1", 65, 60, 0.08, 0.18, 20, 1.0, "Initial scoring-aligned strategy."),
            )


def list_strategy_versions(connection: sqlite3.Connection) -> list[StrategyVersion]:
    rows = connection.execute("select * from strategy_versions order by id desc").fetchall()
    return [_strategy_from_row(row) for row in rows]


def get_active_strategy(connection: sqlite3.Connection) -> StrategyVersion:
    row = connection.execute("select * from strategy_versions where status = 'active'").fetchone()
    if row is None:
        raise RuntimeError("No active strategy version found")
    return _strategy_from_row(row)


def insert_strategy_version(
    connection: sqlite3.Connection,
    *,
    name: str,
    status: str,
    medium_entry_threshold: int,
    short_entry_threshold: int,
    stop_loss_pct: float,
    take_profit_pct: float,
    max_holding_days: int,
    position_size_pct: float,
    notes: str,
) -> StrategyVersion:
    cursor = connection.execute(
        """
        insert into strategy_versions (
            name, status, medium_entry_threshold, short_entry_threshold,
            stop_loss_pct, take_profit_pct, max_holding_days, position_size_pct, notes
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            status,
            medium_entry_threshold,
            short_entry_threshold,
            stop_loss_pct,
            take_profit_pct,
            max_holding_days,
            position_size_pct,
            notes,
        ),
    )
    row = connection.execute("select * from strategy_versions where id = ?", (cursor.lastrowid,)).fetchone()
    return _strategy_from_row(row)


def upsert_historical_bars(connection: sqlite3.Connection, ticker: str, bars: list[DailyBar]) -> None:
    normalized = ticker.upper()
    connection.executemany(
        """
        insert into historical_bars (ticker, date, open, high, low, close, adjusted_close, volume)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(ticker, date) do update set
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            adjusted_close = excluded.adjusted_close,
            volume = excluded.volume
        """,
        [
            (
                normalized,
                bar.date,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.adjusted_close,
                bar.volume,
            )
            for bar in bars
        ],
    )


def get_historical_bars(
    connection: sqlite3.Connection,
    ticker: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[DailyBar]:
    clauses = ["ticker = ?"]
    params: list[Any] = [ticker.upper()]
    if start_date is not None:
        clauses.append("date >= ?")
        params.append(start_date)
    if end_date is not None:
        clauses.append("date <= ?")
        params.append(end_date)
    rows = connection.execute(
        f"select * from historical_bars where {' and '.join(clauses)} order by date",
        params,
    ).fetchall()
    return [_bar_from_row(row) for row in rows]


def insert_backtest_run(
    connection: sqlite3.Connection,
    *,
    strategy_id: int,
    tickers: list[str],
    start_date: str,
    end_date: str,
    initial_cash: float,
) -> int:
    cursor = connection.execute(
        """
        insert into backtest_runs (strategy_id, tickers, start_date, end_date, initial_cash)
        values (?, ?, ?, ?, ?)
        """,
        (strategy_id, ",".join(tickers), start_date, end_date, initial_cash),
    )
    return int(cursor.lastrowid)


def insert_backtest_trade(
    connection: sqlite3.Connection,
    *,
    run_id: int,
    ticker: str,
    entry_date: str,
    exit_date: str,
    entry_price: float,
    exit_price: float,
    shares: float,
    return_pct: float,
    holding_days: int,
    exit_reason: str,
) -> None:
    connection.execute(
        """
        insert into backtest_trades (
            run_id, ticker, entry_date, exit_date, entry_price, exit_price,
            shares, return_pct, holding_days, exit_reason
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, ticker, entry_date, exit_date, entry_price, exit_price, shares, return_pct, holding_days, exit_reason),
    )


def insert_backtest_metrics(
    connection: sqlite3.Connection,
    *,
    run_id: int,
    total_return: float,
    annualized_return: float,
    max_drawdown: float,
    win_rate: float,
    trade_count: int,
    average_holding_days: float,
    buy_hold_return: float,
) -> None:
    connection.execute(
        """
        insert into backtest_metrics (
            run_id, total_return, annualized_return, max_drawdown, win_rate,
            trade_count, average_holding_days, buy_hold_return
        )
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, total_return, annualized_return, max_drawdown, win_rate, trade_count, average_holding_days, buy_hold_return),
    )


def list_backtest_runs(connection: sqlite3.Connection, limit: int = 20) -> list[StoredBacktestRun]:
    rows = connection.execute(
        """
        select
            r.id,
            r.strategy_id,
            r.tickers,
            r.start_date,
            r.end_date,
            r.initial_cash,
            r.created_at,
            m.total_return,
            m.max_drawdown,
            m.win_rate,
            m.trade_count,
            m.buy_hold_return
        from backtest_runs r
        join backtest_metrics m on m.run_id = r.id
        order by r.id desc
        limit ?
        """,
        (limit,),
    ).fetchall()
    return [
        StoredBacktestRun(
            run_id=int(row["id"]),
            strategy_id=int(row["strategy_id"]),
            tickers=[ticker for ticker in row["tickers"].split(",") if ticker],
            start_date=row["start_date"],
            end_date=row["end_date"],
            initial_cash=float(row["initial_cash"]),
            created_at=row["created_at"],
            total_return=float(row["total_return"]),
            max_drawdown=float(row["max_drawdown"]),
            win_rate=float(row["win_rate"]),
            trade_count=int(row["trade_count"]),
            buy_hold_return=float(row["buy_hold_return"]),
        )
        for row in rows
    ]


def insert_evolution_candidate(
    connection: sqlite3.Connection,
    *,
    strategy_id: int,
    training_run_id: int,
    validation_run_id: int,
    active_validation_return: float,
    candidate_validation_return: float,
    max_drawdown: float,
) -> int:
    cursor = connection.execute(
        """
        insert into evolution_candidates (
            strategy_id, training_run_id, validation_run_id,
            active_validation_return, candidate_validation_return, max_drawdown
        )
        values (?, ?, ?, ?, ?, ?)
        """,
        (
            strategy_id,
            training_run_id,
            validation_run_id,
            active_validation_return,
            candidate_validation_return,
            max_drawdown,
        ),
    )
    return int(cursor.lastrowid)


def _strategy_from_row(row: sqlite3.Row) -> StrategyVersion:
    return StrategyVersion(
        strategy_id=int(row["id"]),
        name=row["name"],
        status=row["status"],
        medium_entry_threshold=int(row["medium_entry_threshold"]),
        short_entry_threshold=int(row["short_entry_threshold"]),
        stop_loss_pct=float(row["stop_loss_pct"]),
        take_profit_pct=float(row["take_profit_pct"]),
        max_holding_days=int(row["max_holding_days"]),
        position_size_pct=float(row["position_size_pct"]),
        created_at=row["created_at"],
        notes=row["notes"],
    )


def _bar_from_row(row: sqlite3.Row) -> DailyBar:
    return DailyBar(
        date=row["date"],
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        adjusted_close=float(row["adjusted_close"]),
        volume=int(row["volume"]),
    )

