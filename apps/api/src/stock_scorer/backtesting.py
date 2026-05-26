from dataclasses import dataclass
from math import prod
from typing import Any

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
    max_positions: int = 5
    position_size_pct: float | None = None
    commission_bps: float = 0.0
    slippage_bps: float = 0.0


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
class BacktestDailyEquity:
    date: str
    cash: float
    positions_value: float
    total_equity: float


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
    equity_curve: list[BacktestDailyEquity]


@dataclass(frozen=True)
class OpenPosition:
    ticker: str
    entry_date: str
    entry_price: float
    shares: float
    entry_index: int


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
        bars_by_ticker: dict[str, list[DailyBar]] = {}
        score_snapshots_by_ticker: dict[str, dict[str, dict[str, object]]] = {}

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
            bars_by_ticker[ticker] = bars
            score_snapshots_by_ticker[ticker] = score_snapshots

        portfolio_result = _simulate_portfolio(
            tickers=tickers,
            bars_by_ticker=bars_by_ticker,
            score_snapshots_by_ticker=score_snapshots_by_ticker,
            start_date=request.start_date,
            end_date=request.end_date,
            strategy=selected_strategy,
            initial_cash=request.initial_cash,
            max_positions=request.max_positions,
            position_size_pct=request.position_size_pct,
            commission_bps=request.commission_bps,
            slippage_bps=request.slippage_bps,
        )
        all_trades = portfolio_result["trades"]
        equity_curve = portfolio_result["equity_curve"]
        for trade in all_trades:
            insert_backtest_trade(connection, run_id=run_id, **trade.__dict__)

        metrics = _calculate_metrics(
            initial_cash=request.initial_cash,
            ending_cash=equity_curve[-1].total_equity if equity_curve else request.initial_cash,
            equity_curve=[point.total_equity for point in equity_curve] or [request.initial_cash],
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
        equity_curve=equity_curve,
    )


def _simulate_portfolio(
    *,
    tickers: list[str],
    bars_by_ticker: dict[str, list[DailyBar]],
    score_snapshots_by_ticker: dict[str, dict[str, dict[str, object]]],
    start_date: str,
    end_date: str,
    strategy: StrategyVersion,
    initial_cash: float,
    max_positions: int,
    position_size_pct: float | None,
    commission_bps: float,
    slippage_bps: float,
) -> dict[str, Any]:
    friction = (commission_bps + slippage_bps) / 10_000
    cash = initial_cash
    positions: dict[str, OpenPosition] = {}
    trades: list[BacktestTrade] = []
    equity_curve: list[BacktestDailyEquity] = []
    bar_maps = {
        ticker: {bar.date: bar for bar in bars}
        for ticker, bars in bars_by_ticker.items()
    }
    all_dates = sorted(
        {
            bar.date
            for bars in bars_by_ticker.values()
            for bar in bars
            if start_date <= bar.date <= end_date
        }
    )

    for date_index, current_date in enumerate(all_dates):
        for ticker, position in list(positions.items()):
            bar = bar_maps.get(ticker, {}).get(current_date)
            if bar is None or current_date == position.entry_date:
                continue
            score = _score_for_portfolio_date(ticker, current_date, bars_by_ticker[ticker], score_snapshots_by_ticker.get(ticker, {}))
            if score is None:
                continue
            exit_price = bar.adjusted_close * (1 - friction)
            return_pct = exit_price / position.entry_price - 1
            holding_days = date_index - position.entry_index
            exit_reason = _exit_reason(return_pct, holding_days, score["short_term_label"], strategy)
            if exit_reason:
                cash += position.shares * exit_price
                trades.append(
                    BacktestTrade(
                        ticker=ticker,
                        entry_date=position.entry_date,
                        exit_date=current_date,
                        entry_price=position.entry_price,
                        exit_price=exit_price,
                        shares=position.shares,
                        return_pct=return_pct,
                        holding_days=holding_days,
                        exit_reason=exit_reason,
                    )
                )
                del positions[ticker]

        total_equity_before_entries = cash + _positions_value(positions, bar_maps, current_date, friction)
        for ticker in tickers:
            if len(positions) >= max_positions:
                break
            if ticker in positions:
                continue
            bar = bar_maps.get(ticker, {}).get(current_date)
            if bar is None:
                continue
            score = _score_for_portfolio_date(ticker, current_date, bars_by_ticker[ticker], score_snapshots_by_ticker.get(ticker, {}))
            if score is None:
                continue
            if (
                int(score["medium_term_score"]) >= strategy.medium_entry_threshold
                and int(score["short_term_score"]) >= strategy.short_entry_threshold
            ):
                entry_price = bar.adjusted_close * (1 + friction)
                allocation = position_size_pct if position_size_pct is not None else strategy.position_size_pct
                target_value = min(cash, total_equity_before_entries * allocation)
                if target_value <= 0 or entry_price <= 0:
                    continue
                shares = target_value / entry_price
                cash -= shares * entry_price
                positions[ticker] = OpenPosition(
                    ticker=ticker,
                    entry_date=current_date,
                    entry_price=entry_price,
                    shares=shares,
                    entry_index=date_index,
                )

        positions_value = _positions_value(positions, bar_maps, current_date, friction)
        equity_curve.append(
            BacktestDailyEquity(
                date=current_date,
                cash=cash,
                positions_value=positions_value,
                total_equity=cash + positions_value,
            )
        )

    if all_dates:
        final_date = all_dates[-1]
        final_index = len(all_dates) - 1
        for ticker, position in list(positions.items()):
            bar = _bar_on_or_before(bar_maps.get(ticker, {}), final_date)
            if bar is None:
                continue
            exit_price = bar.adjusted_close * (1 - friction)
            cash += position.shares * exit_price
            trades.append(
                BacktestTrade(
                    ticker=ticker,
                    entry_date=position.entry_date,
                    exit_date=bar.date,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    shares=position.shares,
                    return_pct=exit_price / position.entry_price - 1,
                    holding_days=max(1, final_index - position.entry_index),
                    exit_reason="end_date",
                )
            )
            del positions[ticker]
        equity_curve[-1] = BacktestDailyEquity(
            date=final_date,
            cash=cash,
            positions_value=0.0,
            total_equity=cash,
        )

    return {"trades": trades, "equity_curve": equity_curve}


def _score_for_portfolio_date(
    ticker: str,
    date: str,
    bars: list[DailyBar],
    score_snapshots: dict[str, dict[str, object]],
) -> dict[str, object] | None:
    as_of_bars = [candidate for candidate in bars if candidate.date <= date]
    if len(as_of_bars) < 50:
        return None
    return _score_for_date(ticker, date, as_of_bars, score_snapshots)


def _positions_value(
    positions: dict[str, OpenPosition],
    bar_maps: dict[str, dict[str, DailyBar]],
    current_date: str,
    friction: float,
) -> float:
    value = 0.0
    for ticker, position in positions.items():
        bar = _bar_on_or_before(bar_maps.get(ticker, {}), current_date)
        if bar is not None:
            value += position.shares * bar.adjusted_close * (1 - friction)
    return value


def _bar_on_or_before(bar_map: dict[str, DailyBar], current_date: str) -> DailyBar | None:
    for date in sorted(bar_map, reverse=True):
        if date <= current_date:
            return bar_map[date]
    return None


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
