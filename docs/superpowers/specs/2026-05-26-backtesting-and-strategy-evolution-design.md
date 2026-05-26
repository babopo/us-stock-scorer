# Backtesting and Strategy Evolution Design

## Goal

Build a server-side loop that regularly validates the current scoring strategy against historical data, persists the results, and proposes safer next strategy parameters based on out-of-sample evidence.

## Technology Choice

The first production version uses Python, FastAPI, SQLite, and systemd timers. This matches the current scoring engine and deployment path, keeps the scoring behavior consistent between live analysis and backtests, and avoids adding a second runtime before there is measured compute pressure.

Rust is reserved as a later acceleration boundary. The backtest engine will keep pure data contracts for price bars, strategy parameters, trades, and metrics so a future Rust CLI or PyO3 module can replace the inner simulation loop without changing API routes or admin UI contracts.

SQLite is the first database because this is a single-server personal system, the expected write volume is modest, and the deployment can be durable without operating Postgres. The schema is intentionally relational and can migrate to Postgres later.

## Scope

The first implementation includes:

- A SQLite-backed research store under `apps/api/data/stock_scorer.sqlite3` by default, configurable with `STOCK_SCORER_DB_PATH`.
- Tables for historical bars, backtest runs, trades, metrics, strategy versions, and evolution candidates.
- A deterministic backtest service that replays daily bars using the existing scoring and decision labels.
- A conservative parameter evolution service that searches a small parameter grid and only proposes candidates that beat the active strategy on validation metrics.
- Admin API endpoints to list backtest runs, trigger a run, list strategy versions, and trigger evolution.
- Shared TypeScript client types and React admin panels for operational visibility.
- CLI entry points for scheduled execution.
- systemd service and timer units for production scheduling.

Out of scope for this first implementation:

- Intraday backtesting.
- Full portfolio optimization.
- Automated live trading.
- Unreviewed automatic promotion of evolved parameters.
- Rust implementation before evidence of a bottleneck.

## Strategy Model

Each strategy version stores:

- `medium_entry_threshold`: minimum medium-term score required for a long entry.
- `short_entry_threshold`: minimum short-term score required for a long entry.
- `stop_loss_pct`: exit threshold from entry price.
- `take_profit_pct`: profit-taking threshold from entry price.
- `max_holding_days`: maximum duration before a time exit.
- `position_size_pct`: fraction of equity allocated to one ticker.
- `status`: `active`, `candidate`, or `archived`.

The active version is used for scheduled backtests. Evolution creates candidate versions only. Promotion remains a deliberate admin action in a later step.

## Backtest Flow

1. Load historical bars for requested tickers and date range.
2. For each trading day, build an as-of market snapshot from bars up to that date.
3. Score the snapshot with the existing scoring functions.
4. Enter when medium-term and short-term scores clear the strategy thresholds.
5. Exit on stop loss, take profit, max holding days, or broken short-term signal.
6. Persist run metadata, trades, and aggregate metrics.

Metrics include total return, buy-and-hold return, max drawdown, win rate, trade count, average holding days, and annualized return.

## Evolution Flow

1. Start from the active strategy.
2. Generate a bounded parameter grid around the active thresholds and exits.
3. Run backtests over a training period and validation period.
4. Reject candidates that improve training but fail validation.
5. Persist the best validation candidate as `candidate` with evidence metrics.

The first scoring objective is validation total return minus drawdown penalty. This is simple, auditable, and less prone to overfitting than broad black-box search.

## API Surface

Admin-only endpoints:

- `GET /v1/admin/backtests/runs`
- `POST /v1/admin/backtests/runs`
- `GET /v1/admin/strategies`
- `POST /v1/admin/strategies/evolve`

All routes use the existing admin bearer/session authorization.

## Operations

Scheduled production execution uses systemd units:

- `us-stock-scorer-backtest.service`
- `us-stock-scorer-backtest.timer`

The timer runs the CLI after the US market close window. The CLI remains safe to run manually for deployment verification.

## Testing

Backend tests cover schema initialization, deterministic backtest metrics, evolution candidate generation, admin route authorization, and CLI wiring. TypeScript tests cover client paths and admin UI rendering.

The implementation must pass:

- `apps/api/.venv/bin/python -m pytest -q`
- `pnpm typecheck`
- `pnpm test`

