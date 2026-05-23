# Market Data Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Finnhub and ordered data-source fallback for ticker scoring.

**Architecture:** Keep the current `MarketSnapshot` scoring boundary. Add a Finnhub provider that maps external API responses into `MarketSnapshot`, then route scoring through an ordered provider chain from environment configuration.

**Tech Stack:** FastAPI, httpx, pytest, Python dataclasses.

---

### Task 1: Tests

**Files:**
- Modify: `apps/api/tests/test_market_data.py`
- Modify: `apps/api/tests/test_api.py`

- [ ] Add a Finnhub parsing test using `httpx.MockTransport`.
- [ ] Add a fallback-chain test that monkeypatches the FMP client to fail and Finnhub to succeed.
- [ ] Add a provider-status test for `finnhub`.
- [ ] Run targeted tests and confirm they fail before implementation.

### Task 2: Provider

**Files:**
- Modify: `apps/api/src/stock_scorer/market_data.py`
- Modify: `apps/api/src/stock_scorer/score_service.py`
- Modify: `apps/api/src/stock_scorer/app.py`

- [ ] Add `FinnhubClient`.
- [ ] Add `STOCK_SCORER_DATA_SOURCES` parsing with legacy fallback.
- [ ] Route each provider through the existing `build_score_from_market_snapshot`.
- [ ] Include `finnhub` in admin provider status.

### Task 3: Docs

**Files:**
- Modify: `apps/api/.env.example`
- Modify: `README.md`

- [ ] Document `FINNHUB_API_KEY`.
- [ ] Document ordered fallback configuration.

### Task 4: Verification

- [ ] Run `cd apps/api && .venv/bin/pytest -v`.
- [ ] Run targeted API curl checks if the local server is running.
