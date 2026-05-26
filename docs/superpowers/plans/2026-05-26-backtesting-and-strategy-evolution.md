# Backtesting and Strategy Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scheduled historical backtesting and conservative strategy evolution loop to the existing stock scoring server and admin dashboard.

**Architecture:** Keep the authoritative scoring engine in Python and add a SQLite-backed research subsystem beside the FastAPI app. Expose admin-only APIs and a compact React operations panel, with systemd timer units for production scheduling and a future Rust acceleration boundary.

**Tech Stack:** Python 3.11, FastAPI, SQLite, pytest, TypeScript shared API client, React/Vite admin UI, systemd timer.

---

### Task 1: Research Data Store

**Files:**
- Create: `apps/api/src/stock_scorer/research_store.py`
- Test: `apps/api/tests/test_research_store.py`

- [ ] Create schema initialization for historical bars, backtest runs, trades, metrics, strategy versions, and evolution candidates.
- [ ] Add helpers to resolve `STOCK_SCORER_DB_PATH`, open SQLite connections, seed the default active strategy, insert bars, and read bars by ticker/date range.
- [ ] Verify with pytest that schema creation is idempotent and default strategy seeding creates exactly one active version.

### Task 2: Backtest Engine

**Files:**
- Create: `apps/api/src/stock_scorer/backtesting.py`
- Test: `apps/api/tests/test_backtesting.py`

- [ ] Add deterministic simulation models for requests, trades, metrics, and run summaries.
- [ ] Replay daily bars as-of each trading date using the existing scoring functions.
- [ ] Persist run metadata, trades, and metrics through `research_store`.
- [ ] Verify entry/exit behavior, max drawdown, win rate, and buy-and-hold comparison with fixture bars.

### Task 3: Strategy Evolution

**Files:**
- Create: `apps/api/src/stock_scorer/strategy_evolution.py`
- Test: `apps/api/tests/test_strategy_evolution.py`

- [ ] Generate a bounded parameter grid around the active strategy.
- [ ] Run training and validation backtests for each candidate.
- [ ] Persist only validation-improving candidates as `candidate` strategy versions with evidence metrics.
- [ ] Verify that overfit candidates are rejected and useful candidates are stored.

### Task 4: Admin API and CLI

**Files:**
- Modify: `apps/api/src/stock_scorer/app.py`
- Create: `apps/api/src/stock_scorer/cli.py`
- Modify: `apps/api/pyproject.toml`
- Test: `apps/api/tests/test_api.py`

- [ ] Add admin-only backtest and strategy endpoints.
- [ ] Add `stock-scorer` CLI commands for `backtest run` and `evolve run`.
- [ ] Verify admin authorization, route payloads, and CLI command execution.

### Task 5: Shared Client and Admin UI

**Files:**
- Modify: `packages/api-client/src/types.ts`
- Modify: `packages/api-client/src/client.ts`
- Modify: `packages/api-client/test/client.test.ts`
- Create: `apps/admin/src/features/backtesting/BacktestingPanel.tsx`
- Create: `apps/admin/src/features/backtesting/BacktestingPanel.test.tsx`
- Modify: `apps/admin/src/app/App.tsx`
- Modify: `apps/admin/src/styles.css`

- [ ] Add typed client methods for backtest runs, triggering runs, strategy listing, and evolution.
- [ ] Add a compact admin panel showing recent runs, active/candidate strategies, and manual trigger buttons.
- [ ] Verify client request paths and UI rendering with tests.

### Task 6: Production Scheduling and Docs

**Files:**
- Create: `deploy/systemd/us-stock-scorer-backtest.service`
- Create: `deploy/systemd/us-stock-scorer-backtest.timer`
- Modify: `deploy/install-production.sh`
- Modify: `README.md`
- Modify: `docs/deployment/nginx.md`

- [ ] Install systemd service and timer units in the production script.
- [ ] Keep DB path under the production app directory unless `STOCK_SCORER_DB_PATH` is already configured.
- [ ] Document manual and scheduled backtest operations.
- [ ] Verify backend tests, typecheck, frontend tests, production install script syntax, deployed services, and HTTP health checks.

