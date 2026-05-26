from dataclasses import dataclass
from math import prod

from stock_scorer.live_scoring import build_score_from_market_snapshot
from stock_scorer.market_data import DailyBar, MarketSnapshot
from stock_scorer.research_store import (
    StrategyVersion,
    get_active_strategy,
    get_historical_bars,
    get_score_snapshots,
    initialize_research_store,
    insert_backtest_metrics,
    insert_backtest_run,
    insert_backtest_trade,
    open_research_connection,
)


@dataclass(frozen=True)
class BacktestRequest:
    tickers: list[str]
    start_date: str
    end_date: str
    initial_cash: float = 10_000.0
    strategy_id: int | None = None


@dataclass(frozen=True)
class BacktestTrade:
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    shares: float
    return_pct: float
    holding_days: int
    exit_reason: str


@dataclass(frozen=True)
class BacktestMetrics:
    total_return: float
    annualized_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    average_holding_days: float
    buy_hold_return: float


@dataclass(frozen=True)
class BacktestSummary:
    run_id: int
    strategy_id: int
    tickers: list[str]
    start_date: str
    end_date: str
    initial_cash: float
    metrics: BacktestMetrics
    trades: list[BacktestTrade]


def run_backtest(request: BacktestRequest, strategy: StrategyVersion | None = None) -> BacktestSummary:
    initialize_research_store()
    tickers = [ticker.upper() for ticker in request.tickers]
    with open_research_connection() as connection:
        selected_strategy = strategy or get_active_strategy(connection)
        run_id = insert_backtest_run(
            connection,
            strategy_id=selected_strategy.strategy_id,
            tickers=tickers,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_cash=request.initial_cash,
        )
        all_trades: list[BacktestTrade] = []
        buy_hold_returns: list[float] = []
        equity_curve = [request.initial_cash]
        cash = request.initial_cash

        for ticker in tickers:
            bars = get_historical_bars(connection, ticker, None, request.end_date)
            if not bars:
                bars = _hydrate_historical_bars(connection, ticker, request.end_date)
            if not bars:
                continue
            score_snapshots = {
                snapshot.date: snapshot.score
                for snapshot in get_score_snapshots(connection, ticker, limit=10_000)
                if request.start_date <= snapshot.date <= request.end_date
            }
            window_bars = [bar for bar in bars if request.start_date <= bar.date <= request.end_date]
            if len(window_bars) >= 2 and window_bars[0].adjusted_close:
                buy_hold_returns.append(window_bars[-1].adjusted_close / window_bars[0].adjusted_close - 1)
            trades = _simulate_ticker(
                ticker,
                bars,
                request.start_date,
                request.end_date,
                selected_strategy,
                cash,
                score_snapshots,
            )
            for trade in trades:
                cash += trade.shares * (trade.exit_price - trade.entry_price)
                equity_curve.append(cash)
                all_trades.append(trade)
                insert_backtest_trade(connection, run_id=run_id, **trade.__dict__)

        metrics = _calculate_metrics(
            initial_cash=request.initial_cash,
            ending_cash=cash,
            equity_curve=equity_curve,
            trades=all_trades,
            buy_hold_return=sum(buy_hold_returns) / len(buy_hold_returns) if buy_hold_returns else 0.0,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        insert_backtest_metrics(connection, run_id=run_id, **metrics.__dict__)

    return BacktestSummary(
        run_id=run_id,
        strategy_id=selected_strategy.strategy_id,
        tickers=tickers,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_cash=request.initial_cash,
        metrics=metrics,
        trades=all_trades,
    )


def _hydrate_historical_bars(connection: object, ticker: str, end_date: str) -> list[DailyBar]:
    from stock_scorer.score_service import fetch_market_snapshot_from_source, get_configured_data_sources
    from stock_scorer.research_store import upsert_historical_bars

    for source in get_configured_data_sources():
        if source in {"fixture", "fixtures"}:
            continue
        try:
            snapshot = fetch_market_snapshot_from_source(source, ticker)
        except Exception:
            continue
        bars = [bar for bar in snapshot.daily_bars if bar.date <= end_date]
        if bars:
            upsert_historical_bars(connection, ticker, bars)
            return sorted(bars, key=lambda bar: bar.date)
    return []


def _simulate_ticker(
    ticker: str,
    all_bars: list[DailyBar],
    start_date: str,
    end_date: str,
    strategy: StrategyVersion,
    cash: float,
    score_snapshots: dict[str, dict[str, object]] | None = None,
) -> list[BacktestTrade]:
    trades: list[BacktestTrade] = []
    score_snapshots = score_snapshots or {}
    dated_bars = [bar for bar in all_bars if start_date <= bar.date <= end_date]
    open_trade: tuple[DailyBar, float] | None = None
    for index, bar in enumerate(dated_bars):
        as_of_bars = [candidate for candidate in all_bars if candidate.date <= bar.date]
        if len(as_of_bars) < 50:
            continue
        score = _score_for_date(ticker, bar.date, as_of_bars, score_snapshots)
        if open_trade is None:
            if (
                int(score["medium_term_score"]) >= strategy.medium_entry_threshold
                and int(score["short_term_score"]) >= strategy.short_entry_threshold
            ):
                shares = (cash * strategy.position_size_pct) / bar.adjusted_close if bar.adjusted_close else 0.0
                open_trade = (bar, shares)
            continue

        entry_bar, shares = open_trade
        holding_days = index - dated_bars.index(entry_bar)
        return_pct = bar.adjusted_close / entry_bar.adjusted_close - 1
        exit_reason = _exit_reason(return_pct, holding_days, score["short_term_label"], strategy)
        if exit_reason:
            trades.append(
                BacktestTrade(
                    ticker=ticker,
                    entry_date=entry_bar.date,
                    exit_date=bar.date,
                    entry_price=entry_bar.adjusted_close,
                    exit_price=bar.adjusted_close,
                    shares=shares,
                    return_pct=return_pct,
                    holding_days=holding_days,
                    exit_reason=exit_reason,
                )
            )
            open_trade = None

    if open_trade is not None and dated_bars:
        entry_bar, shares = open_trade
        exit_bar = dated_bars[-1]
        trades.append(
            BacktestTrade(
                ticker=ticker,
                entry_date=entry_bar.date,
                exit_date=exit_bar.date,
                entry_price=entry_bar.adjusted_close,
                exit_price=exit_bar.adjusted_close,
                shares=shares,
                return_pct=exit_bar.adjusted_close / entry_bar.adjusted_close - 1,
                holding_days=max(1, len(dated_bars) - dated_bars.index(entry_bar) - 1),
                exit_reason="end_date",
            )
        )
    return trades


def _score_for_date(
    ticker: str,
    date: str,
    as_of_bars: list[DailyBar],
    score_snapshots: dict[str, dict[str, object]],
) -> dict[str, object]:
    snapshot_score = score_snapshots.get(date)
    if snapshot_score is not None:
        return snapshot_score
    return build_score_from_market_snapshot(_snapshot_from_bars(ticker, as_of_bars)).model_dump(mode="json")


def _snapshot_from_bars(ticker: str, bars_ascending: list[DailyBar]) -> MarketSnapshot:
    bars_descending = sorted(bars_ascending, key=lambda bar: bar.date, reverse=True)
    latest = bars_descending[0]
    return MarketSnapshot(
        ticker=ticker,
        company_name=ticker,
        last_price=latest.adjusted_close,
        data_as_of=latest.date,
        daily_bars=bars_descending,
        overview={
            "ProfitMargin": "0.22",
            "ReturnOnEquityTTM": "0.24",
            "ForwardPE": "24",
            "QuarterlyRevenueGrowthYOY": "0.12",
            "QuarterlyEarningsGrowthYOY": "0.16",
            "DebtToEquity": "0.6",
            "InterestCoverage": "12",
        },
        source="backtest",
    )


def _exit_reason(return_pct: float, holding_days: int, short_label: object, strategy: StrategyVersion) -> str | None:
    if return_pct <= -strategy.stop_loss_pct:
        return "stop_loss"
    if return_pct >= strategy.take_profit_pct:
        return "take_profit"
    if holding_days >= strategy.max_holding_days:
        return "max_holding_days"
    if str(short_label) == "avoid":
        return "signal_exit"
    return None


def _calculate_metrics(
    *,
    initial_cash: float,
    ending_cash: float,
    equity_curve: list[float],
    trades: list[BacktestTrade],
    buy_hold_return: float,
    start_date: str,
    end_date: str,
) -> BacktestMetrics:
    total_return = ending_cash / initial_cash - 1 if initial_cash else 0.0
    trade_count = len(trades)
    wins = [trade for trade in trades if trade.return_pct > 0]
    average_holding_days = sum(trade.holding_days for trade in trades) / trade_count if trade_count else 0.0
    annualized_return = _annualized_return(total_return, start_date, end_date)
    return BacktestMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        max_drawdown=_max_drawdown(equity_curve),
        win_rate=len(wins) / trade_count if trade_count else 0.0,
        trade_count=trade_count,
        average_holding_days=average_holding_days,
        buy_hold_return=buy_hold_return,
    )


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0] if equity_curve else 0.0
    drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak:
            drawdown = min(drawdown, value / peak - 1)
    return abs(drawdown)


def _annualized_return(total_return: float, start_date: str, end_date: str) -> float:
    start_year, start_month, start_day = [int(part) for part in start_date.split("-")]
    end_year, end_month, end_day = [int(part) for part in end_date.split("-")]
    days = max(1, (end_year - start_year) * 365 + (end_month - start_month) * 30 + (end_day - start_day))
    periods = 365 / days
    return prod([1 + total_return] * 1) ** periods - 1 if total_return > -1 else -1.0
