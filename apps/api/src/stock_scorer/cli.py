import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import date, timedelta
from typing import Any

from stock_scorer.backtesting import BacktestRequest, run_backtest
from stock_scorer.strategy_evolution import EvolutionRequest, evolve_strategy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stock-scorer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest = subparsers.add_parser("backtest")
    backtest_subparsers = backtest.add_subparsers(dest="subcommand", required=True)
    backtest_run = backtest_subparsers.add_parser("run")
    backtest_run.add_argument("--tickers", required=True)
    backtest_run.add_argument("--start-date")
    backtest_run.add_argument("--end-date")
    backtest_run.add_argument("--initial-cash", type=float, default=10_000.0)

    evolve = subparsers.add_parser("evolve")
    evolve_subparsers = evolve.add_subparsers(dest="subcommand", required=True)
    evolve_run = evolve_subparsers.add_parser("run")
    evolve_run.add_argument("--tickers", required=True)
    evolve_run.add_argument("--training-start-date")
    evolve_run.add_argument("--training-end-date")
    evolve_run.add_argument("--validation-start-date")
    evolve_run.add_argument("--validation-end-date")
    evolve_run.add_argument("--initial-cash", type=float, default=10_000.0)

    args = parser.parse_args(argv)
    if args.command == "backtest" and args.subcommand == "run":
        end_date = args.end_date or date.today().isoformat()
        start_date = args.start_date or (date.fromisoformat(end_date) - timedelta(days=365)).isoformat()
        result = run_backtest(
            BacktestRequest(
                tickers=_tickers(args.tickers),
                start_date=start_date,
                end_date=end_date,
                initial_cash=args.initial_cash,
            )
        )
    elif args.command == "evolve" and args.subcommand == "run":
        validation_end_date = args.validation_end_date or date.today().isoformat()
        validation_start_date = args.validation_start_date or (
            date.fromisoformat(validation_end_date) - timedelta(days=120)
        ).isoformat()
        training_end_date = args.training_end_date or validation_start_date
        training_start_date = args.training_start_date or (
            date.fromisoformat(training_end_date) - timedelta(days=240)
        ).isoformat()
        result = evolve_strategy(
            EvolutionRequest(
                tickers=_tickers(args.tickers),
                training_start_date=training_start_date,
                training_end_date=training_end_date,
                validation_start_date=validation_start_date,
                validation_end_date=validation_end_date,
                initial_cash=args.initial_cash,
            )
        )
    else:
        parser.error("Unsupported command")

    print(json.dumps(_jsonable(result), ensure_ascii=False, indent=2))
    return 0


def _tickers(raw: str) -> list[str]:
    tickers = [ticker.strip().upper() for ticker in raw.split(",") if ticker.strip()]
    if not tickers:
        raise SystemExit("--tickers must include at least one ticker")
    return tickers


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


if __name__ == "__main__":
    raise SystemExit(main())
