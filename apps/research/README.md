# Research

This folder is for local experiments before production code changes.

The production research loop now lives in the API package:

- `apps/api/src/stock_scorer/research_store.py` stores strategy versions, historical bars, sync runs, score snapshots and backtest runs in SQLite.
- `apps/api/src/stock_scorer/history_sync.py` syncs historical EOD bars and writes historical score snapshots.
- `apps/api/src/stock_scorer/backtesting.py` runs deterministic backtests against stored history.
- `apps/api/src/stock_scorer/strategy_evolution.py` generates candidate strategy versions from a conservative parameter grid.
- `apps/api/src/stock_scorer/cli.py` exposes `stock-scorer history sync`, `stock-scorer backtest run` and `stock-scorer evolve run`.

Use this folder for research that is not ready for those production modules yet. A good research sequence is still:

1. Build a 20-50 ticker watchlist.
2. Compare fixture output against manual judgment.
3. Add real data ingestion in a separate task.
4. Store daily score snapshots before doing 5-year backtests.

When an experiment graduates, move it into the API package and cover it with `apps/api/.venv/bin/python -m pytest -q`.
