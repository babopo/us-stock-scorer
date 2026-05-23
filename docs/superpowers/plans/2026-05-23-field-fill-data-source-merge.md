# Field-Fill Data Source Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Request all configured live data sources and score from a priority-merged snapshot whose missing overview fields are filled from later providers.

**Architecture:** Keep provider fetch logic in `stock_scorer.score_service`. Add a small merge helper that accepts successful `(source, MarketSnapshot)` pairs, uses the first real success as the primary snapshot for price and history, and fills `overview` fields by source priority. Reuse existing scoring and error mapping so the API contract stays stable.

**Tech Stack:** Python, FastAPI service layer, Pydantic models, pytest, httpx-free unit tests using monkeypatch.

---

### Task 1: Service Tests For Field-Fill Aggregation

**Files:**
- Modify: `apps/api/tests/test_api.py`
- Test: `apps/api/tests/test_api.py`

- [x] **Step 1: Write failing test for requesting later providers and filling missing overview fields**

Add these imports near the existing imports:

```python
from datetime import date, timedelta

from stock_scorer.market_data import DailyBar, MarketSnapshot
```

Add this helper near the tests:

```python
def market_snapshot(source: str, overview: dict[str, object], last_price: float = 100.0) -> MarketSnapshot:
    first_day = date(2026, 5, 20)
    bars = [
        DailyBar(
            date=(first_day - timedelta(days=index)).isoformat(),
            open=100.0 - index,
            high=101.0 - index,
            low=99.0 - index,
            close=100.0 - index,
            adjusted_close=100.0 - index,
            volume=1_000_000,
        )
        for index in range(60)
    ]
    return MarketSnapshot(
        ticker="MSFT",
        company_name=f"{source} Microsoft",
        last_price=last_price,
        data_as_of="2026-05-20",
        daily_bars=bars,
        overview=overview,
        source=source,
    )
```

Add this fake client helper near `market_snapshot`:

```python
class FakeSnapshotClient:
    def __init__(self, source: str, snapshot: MarketSnapshot | Exception, calls: list[str]):
        self._source = source
        self._snapshot = snapshot
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    def fetch_snapshot(self, ticker: str) -> MarketSnapshot:
        self._calls.append(self._source)
        if isinstance(self._snapshot, Exception):
            raise self._snapshot
        return self._snapshot
```

Add this test after the existing fallback test:

```python
def test_score_endpoint_fills_missing_primary_fields_from_later_sources(monkeypatch):
    calls: list[str] = []
    fmp_snapshot = market_snapshot(
        "fmp",
        {
            "PERatio": None,
            "ForwardPE": "",
            "ProfitMargin": "0.25",
            "MarketCapitalization": "2500000000000",
        },
        last_price=321.0,
    )
    finnhub_snapshot = market_snapshot(
        "finnhub",
        {
            "PERatio": "28.5",
            "ForwardPE": "24.2",
            "Beta": "0.92",
        },
        last_price=999.0,
    )

    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCES", "fmp,finnhub")
    monkeypatch.setenv("FMP_API_KEY", "secret-fmp-key")
    monkeypatch.setenv("FINNHUB_API_KEY", "secret-finnhub-key")
    monkeypatch.setattr(
        score_service,
        "FmpClient",
        lambda *args, **kwargs: FakeSnapshotClient("fmp", fmp_snapshot, calls),
    )
    monkeypatch.setattr(
        score_service,
        "FinnhubClient",
        lambda *args, **kwargs: FakeSnapshotClient("finnhub", finnhub_snapshot, calls),
    )

    response = client.get("/v1/stocks/MSFT/score", headers=read_auth_headers(monkeypatch))

    assert response.status_code == 200
    payload = response.json()
    assert calls == ["fmp", "finnhub"]
    assert payload["last_price"] == 321.0
    assert payload["data_source"] == "fmp+finnhub"
    valuation = next(factor for factor in payload["factors"] if factor["name"] == "估值")
    assert valuation["score"] > 50
    assert "PE/Forward PE 约 24.2" in valuation["evidence"][0]
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/api && .venv/bin/python -m pytest tests/test_api.py::test_score_endpoint_fills_missing_primary_fields_from_later_sources -q
```

Expected: FAIL because the current fallback behavior returns after FMP and never requests Finnhub.

- [x] **Step 3: Write failing test for later provider failure remaining recoverable**

Add this test after the field-fill test:

```python
def test_score_endpoint_ignores_later_provider_failure_when_primary_succeeds(monkeypatch):
    calls: list[str] = []
    fmp_snapshot = market_snapshot(
        "fmp",
        {
            "PERatio": "20",
            "ProfitMargin": "0.25",
            "MarketCapitalization": "2500000000000",
        },
        last_price=321.0,
    )

    monkeypatch.setenv("STOCK_SCORER_DATA_SOURCES", "fmp,finnhub")
    monkeypatch.setenv("FMP_API_KEY", "secret-fmp-key")
    monkeypatch.setenv("FINNHUB_API_KEY", "secret-finnhub-key")
    monkeypatch.setattr(
        score_service,
        "FmpClient",
        lambda *args, **kwargs: FakeSnapshotClient("fmp", fmp_snapshot, calls),
    )
    monkeypatch.setattr(
        score_service,
        "FinnhubClient",
        lambda *args, **kwargs: FakeSnapshotClient(
            "finnhub",
            MarketDataRateLimited("Finnhub rate limit exceeded"),
            calls,
        ),
    )

    response = client.get("/v1/stocks/MSFT/score", headers=read_auth_headers(monkeypatch))

    assert response.status_code == 200
    assert response.json()["data_source"] == "fmp"
    assert calls == ["fmp", "finnhub"]
```

- [x] **Step 4: Run second test to verify it fails**

Run:

```bash
cd apps/api && .venv/bin/python -m pytest tests/test_api.py::test_score_endpoint_ignores_later_provider_failure_when_primary_succeeds -q
```

Expected: FAIL because the current fallback behavior returns after FMP and never requests Finnhub.

### Task 2: Implement Snapshot Fetching And Merge

**Files:**
- Modify: `apps/api/src/stock_scorer/score_service.py`
- Test: `apps/api/tests/test_api.py`

- [x] **Step 1: Add snapshot fetch helper and merge helper**

In `apps/api/src/stock_scorer/score_service.py`, import `MarketSnapshot`:

```python
from stock_scorer.market_data import (
    AlphaVantageClient,
    FinnhubClient,
    FmpClient,
    MarketDataConfigurationError,
    MarketDataError,
    MarketDataNotFound,
    MarketDataUnavailable,
    MarketSnapshot,
)
```

Add these helpers below `_format_fallback_failures`:

```python
def fetch_market_snapshot_from_source(source: str, ticker: str) -> MarketSnapshot:
    source = _normalize_source(source)
    if source in {"alpha_vantage", "alphavantage"}:
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
        with AlphaVantageClient(api_key=api_key) as client:
            return client.fetch_snapshot(ticker)
    if source == "fmp":
        api_key = os.getenv("FMP_API_KEY", "")
        with FmpClient(api_key=api_key) as client:
            return client.fetch_snapshot(ticker)
    if source == "finnhub":
        api_key = os.getenv("FINNHUB_API_KEY", "")
        with FinnhubClient(api_key=api_key) as client:
            return client.fetch_snapshot(ticker)
    raise MarketDataConfigurationError(f"Unsupported STOCK_SCORER_DATA_SOURCE: {source}")
```

```python
def merge_market_snapshots(snapshots: list[MarketSnapshot]) -> MarketSnapshot:
    if not snapshots:
        raise MarketDataUnavailable("No successful market snapshots to merge")
    primary = snapshots[0]
    merged_overview: dict[str, object] = {}
    for snapshot in snapshots:
        for key, value in snapshot.overview.items():
            if key not in merged_overview and _has_provider_value(value):
                merged_overview[key] = value
    return MarketSnapshot(
        ticker=primary.ticker,
        company_name=primary.company_name,
        last_price=primary.last_price,
        data_as_of=primary.data_as_of,
        daily_bars=primary.daily_bars,
        overview=merged_overview,
        source="+".join(snapshot.source for snapshot in snapshots),
    )
```

```python
def _has_provider_value(value: object) -> bool:
    return value not in (None, "", "None", "-")
```

- [x] **Step 2: Change `get_stock_score` to aggregate real snapshots**

Replace the body of `get_stock_score` with:

```python
def get_stock_score(ticker: str) -> StockScoreResponse:
    sources = get_configured_data_sources()
    if len(sources) == 1 and sources[0] in {"fixture", "fixtures"}:
        return get_fixture_stock_score(ticker)

    failures: list[tuple[str, Exception]] = []
    snapshots: list[MarketSnapshot] = []
    fixture_score: StockScoreResponse | None = None
    for source in sources:
        try:
            if source in {"fixture", "fixtures"}:
                fixture_score = get_fixture_stock_score(ticker)
                continue
            snapshots.append(fetch_market_snapshot_from_source(source, ticker))
        except (KeyError, MarketDataError) as exc:
            failures.append((source, exc))

    if snapshots:
        return build_score_from_market_snapshot(merge_market_snapshots(snapshots))
    if fixture_score is not None:
        return fixture_score

    if len(failures) == 1:
        raise failures[0][1]
    if all(isinstance(error, MarketDataConfigurationError) for _, error in failures):
        raise MarketDataConfigurationError(_format_fallback_failures(ticker, failures))
    if all(isinstance(error, (KeyError, MarketDataNotFound)) for _, error in failures):
        raise MarketDataNotFound(_format_fallback_failures(ticker, failures))
    raise MarketDataUnavailable(_format_fallback_failures(ticker, failures))
```

- [x] **Step 3: Keep existing source-specific scoring helpers compatible**

Replace `get_alpha_vantage_stock_score`, `get_fmp_stock_score`, and `get_finnhub_stock_score` with wrappers that use the new snapshot helper:

```python
def get_alpha_vantage_stock_score(ticker: str) -> StockScoreResponse:
    return build_score_from_market_snapshot(fetch_market_snapshot_from_source("alpha_vantage", ticker))
```

```python
def get_fmp_stock_score(ticker: str) -> StockScoreResponse:
    return build_score_from_market_snapshot(fetch_market_snapshot_from_source("fmp", ticker))
```

```python
def get_finnhub_stock_score(ticker: str) -> StockScoreResponse:
    return build_score_from_market_snapshot(fetch_market_snapshot_from_source("finnhub", ticker))
```

- [x] **Step 4: Run focused tests to verify pass**

Run:

```bash
cd apps/api && .venv/bin/python -m pytest tests/test_api.py::test_score_endpoint_fills_missing_primary_fields_from_later_sources tests/test_api.py::test_score_endpoint_ignores_later_provider_failure_when_primary_succeeds -q
```

Expected: PASS.

### Task 3: Preserve Existing Fallback And Provider Behavior

**Files:**
- Modify: `apps/api/tests/test_api.py`
- Modify: `apps/api/src/stock_scorer/score_service.py`

- [x] **Step 1: Update existing fallback test monkeypatches**

In `test_score_endpoint_falls_back_to_finnhub_when_fmp_is_rate_limited`, monkeypatch `fetch_market_snapshot_from_source` instead of `get_fmp_stock_score` and `get_finnhub_stock_score`:

```python
def fetch_by_source(source: str, ticker: str):
    if source == "fmp":
        raise MarketDataRateLimited("FMP rate limit exceeded")
    if source == "finnhub":
        return market_snapshot(
            "finnhub",
            {
                "PERatio": "28.5",
                "ProfitMargin": "0.25",
                "MarketCapitalization": "2500000000000",
            },
        )
    raise AssertionError(source)

monkeypatch.setattr(score_service, "fetch_market_snapshot_from_source", fetch_by_source)
```

Keep the final assertion:

```python
assert response.json()["data_source"] == "finnhub"
```

- [x] **Step 2: Run API tests**

Run:

```bash
cd apps/api && .venv/bin/python -m pytest tests/test_api.py -q
```

Expected: PASS.

- [x] **Step 3: Run market-data tests**

Run:

```bash
cd apps/api && .venv/bin/python -m pytest tests/test_market_data.py -q
```

Expected: PASS.

### Task 4: Final Verification

**Files:**
- No new code files.

- [x] **Step 1: Run full API test suite**

Run:

```bash
cd apps/api && .venv/bin/python -m pytest -q
```

Expected: PASS.

- [x] **Step 2: Run repository status check**

Run:

```bash
git status --short
```

Expected: only intentional changes in `apps/api/src/stock_scorer/score_service.py`, `apps/api/tests/test_api.py`, and this plan file.
