# Dual-Horizon Stock Scorer MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a monorepo MVP that returns explainable medium-term and 1-2 week short-term US stock timing decisions from deterministic fixture data, then displays the result in a WeChat Mini Program.

**Architecture:** The backend owns all scoring, data normalization, and API responses. The mini program is a thin client that queries one ticker endpoint and renders scores, evidence, triggers, invalidation conditions, and risks. The first implementation uses local fixture data so tests can lock behavior before connecting paid or free market-data APIs.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pytest, native WeChat Mini Program JavaScript/WXML/WXSS.

---

## File Structure

```text
apps/api/
  pyproject.toml
  src/stock_scorer/__init__.py
  src/stock_scorer/app.py
  src/stock_scorer/models.py
  src/stock_scorer/scoring.py
  src/stock_scorer/fixtures.py
  fixtures/stocks.json
  tests/test_scoring.py
  tests/test_api.py
apps/miniprogram/
  project.config.json
  app.js
  app.json
  app.wxss
  pages/index/index.js
  pages/index/index.json
  pages/index/index.wxml
  pages/index/index.wxss
apps/research/
  README.md
packages/shared/
  README.md
```

## Task 1: Backend Project Skeleton

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/src/stock_scorer/__init__.py`
- Create: `apps/api/tests/test_scoring.py`

- [ ] **Step 1: Create the backend package config**

Create `apps/api/pyproject.toml`:

```toml
[project]
name = "stock-scorer-api"
version = "0.1.0"
description = "Dual-horizon US stock scoring API"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.111,<1.0",
  "pydantic>=2.7,<3.0",
  "uvicorn[standard]>=0.30,<1.0"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2,<9.0",
  "httpx>=0.27,<1.0"
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Create the package marker**

Create `apps/api/src/stock_scorer/__init__.py`:

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

- [ ] **Step 3: Write the first failing scoring test**

Create `apps/api/tests/test_scoring.py`:

```python
from stock_scorer.scoring import classify_medium_term_score


def test_classify_medium_term_score_strong():
    assert classify_medium_term_score(82) == "strong"
```

- [ ] **Step 4: Run the test and verify it fails**

Run:

```bash
cd apps/api
python -m pip install -e ".[dev]"
pytest tests/test_scoring.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'stock_scorer.scoring'`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/pyproject.toml apps/api/src/stock_scorer/__init__.py apps/api/tests/test_scoring.py
git commit -m "chore: add backend package skeleton"
```

## Task 2: Scoring Domain Models

**Files:**
- Create: `apps/api/src/stock_scorer/models.py`
- Modify: `apps/api/tests/test_scoring.py`

- [ ] **Step 1: Extend tests for score labels and action decisions**

Replace `apps/api/tests/test_scoring.py` with:

```python
from stock_scorer.models import ActionDecision, HorizonLabel, ShortTermLabel
from stock_scorer.scoring import (
    classify_medium_term_score,
    classify_short_term_state,
    decide_action,
)


def test_classify_medium_term_score_strong():
    assert classify_medium_term_score(82) == HorizonLabel.STRONG


def test_classify_medium_term_score_weak():
    assert classify_medium_term_score(42) == HorizonLabel.WEAK


def test_classify_short_term_wait_pullback_when_overheated():
    assert classify_short_term_state(score=74, overheated=True, broken_trend=False) == ShortTermLabel.WAIT_PULLBACK


def test_decide_action_strong_medium_and_wait_pullback():
    decision = decide_action(HorizonLabel.STRONG, ShortTermLabel.WAIT_PULLBACK)

    assert decision.action == ActionDecision.WAIT
    assert "不追高" in decision.summary
```

- [ ] **Step 2: Run tests and verify they fail on missing models**

Run:

```bash
cd apps/api
pytest tests/test_scoring.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'stock_scorer.models'`.

- [ ] **Step 3: Create domain models**

Create `apps/api/src/stock_scorer/models.py`:

```python
from enum import StrEnum

from pydantic import BaseModel, Field


class HorizonLabel(StrEnum):
    STRONG = "strong"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    WEAK = "weak"
    AVOID = "avoid"


class ShortTermLabel(StrEnum):
    ENTRY = "entry"
    PROBE = "probe"
    WAIT_PULLBACK = "wait_pullback"
    WAIT_BREAKOUT = "wait_breakout"
    AVOID = "avoid"


class ActionDecision(StrEnum):
    BUY_IN_TRANCHES = "buy_in_tranches"
    SMALL_PROBE = "small_probe"
    WAIT = "wait"
    SHORT_TERM_ONLY = "short_term_only"
    AVOID = "avoid"


class FactorScore(BaseModel):
    name: str
    score: int = Field(ge=0, le=100)
    evidence: list[str]


class Decision(BaseModel):
    action: ActionDecision
    summary: str
    trigger_conditions: list[str]
    invalidation_conditions: list[str]
    risks: list[str]


class StockScoreResponse(BaseModel):
    ticker: str
    company_name: str
    last_price: float
    medium_term_score: int = Field(ge=0, le=100)
    medium_term_label: HorizonLabel
    short_term_score: int = Field(ge=0, le=100)
    short_term_label: ShortTermLabel
    factors: list[FactorScore]
    decision: Decision
    data_as_of: str
```

- [ ] **Step 4: Run tests and verify they fail on missing scoring functions**

Run:

```bash
cd apps/api
pytest tests/test_scoring.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'stock_scorer.scoring'`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/stock_scorer/models.py apps/api/tests/test_scoring.py
git commit -m "feat: define scoring domain models"
```

## Task 3: Deterministic Scoring Rules

**Files:**
- Create: `apps/api/src/stock_scorer/scoring.py`
- Modify: `apps/api/tests/test_scoring.py`

- [ ] **Step 1: Add full rule tests**

Append to `apps/api/tests/test_scoring.py`:

```python

def test_decide_action_strong_medium_and_entry():
    decision = decide_action(HorizonLabel.STRONG, ShortTermLabel.ENTRY)

    assert decision.action == ActionDecision.BUY_IN_TRANCHES
    assert "分批" in decision.summary
    assert decision.trigger_conditions
    assert decision.invalidation_conditions
    assert decision.risks


def test_decide_action_weak_medium_and_entry_is_short_term_only():
    decision = decide_action(HorizonLabel.WEAK, ShortTermLabel.ENTRY)

    assert decision.action == ActionDecision.SHORT_TERM_ONLY
    assert "短线" in decision.summary
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd apps/api
pytest tests/test_scoring.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'stock_scorer.scoring'`.

- [ ] **Step 3: Implement deterministic scoring rules**

Create `apps/api/src/stock_scorer/scoring.py`:

```python
from stock_scorer.models import ActionDecision, Decision, HorizonLabel, ShortTermLabel


def classify_medium_term_score(score: int) -> HorizonLabel:
    if score >= 80:
        return HorizonLabel.STRONG
    if score >= 65:
        return HorizonLabel.POSITIVE
    if score >= 50:
        return HorizonLabel.NEUTRAL
    if score >= 35:
        return HorizonLabel.WEAK
    return HorizonLabel.AVOID


def classify_short_term_state(score: int, overheated: bool, broken_trend: bool) -> ShortTermLabel:
    if broken_trend:
        return ShortTermLabel.AVOID
    if overheated:
        return ShortTermLabel.WAIT_PULLBACK
    if score >= 75:
        return ShortTermLabel.ENTRY
    if score >= 60:
        return ShortTermLabel.PROBE
    if score >= 45:
        return ShortTermLabel.WAIT_BREAKOUT
    return ShortTermLabel.AVOID


def decide_action(medium: HorizonLabel, short: ShortTermLabel) -> Decision:
    if medium in {HorizonLabel.STRONG, HorizonLabel.POSITIVE} and short == ShortTermLabel.ENTRY:
        return Decision(
            action=ActionDecision.BUY_IN_TRANCHES,
            summary="中长期质量较强，短期买点也确认，适合分批买入。",
            trigger_conditions=["短期趋势保持在 20 日均线上方", "相对 SPY 或 QQQ 维持强势"],
            invalidation_conditions=["跌破 50 日均线后无法快速收复", "下一次财报后盈利预期明显下修"],
            risks=["单只股票波动可能显著高于指数", "若大盘转弱，短期信号可靠性下降"],
        )
    if medium in {HorizonLabel.STRONG, HorizonLabel.POSITIVE} and short == ShortTermLabel.WAIT_PULLBACK:
        return Decision(
            action=ActionDecision.WAIT,
            summary="好公司但短期偏热，不追高，等待回调或新的突破确认。",
            trigger_conditions=["回踩 20 日均线附近企稳", "放量突破最近压力位"],
            invalidation_conditions=["跌破 50 日均线且相对强弱转弱", "基本面预期下修"],
            risks=["短期涨幅过大后可能出现估值压缩", "事件窗口可能放大波动"],
        )
    if medium in {HorizonLabel.WEAK, HorizonLabel.AVOID} and short in {ShortTermLabel.ENTRY, ShortTermLabel.PROBE}:
        return Decision(
            action=ActionDecision.SHORT_TERM_ONLY,
            summary="短期信号可交易，但中长期质量不足，只适合短线观察，不进入长期仓位。",
            trigger_conditions=["短期趋势继续保持强势", "成交量支持突破"],
            invalidation_conditions=["跌回突破位下方", "放量下跌并跌破 20 日均线"],
            risks=["基本面较弱会降低反弹延续性", "不适合扩大为长期仓位"],
        )
    if short == ShortTermLabel.PROBE and medium == HorizonLabel.NEUTRAL:
        return Decision(
            action=ActionDecision.SMALL_PROBE,
            summary="中长期中性，短期条件尚可，可以小仓观察。",
            trigger_conditions=["价格站稳 20 日均线", "行业 ETF 同步走强"],
            invalidation_conditions=["跌破最近 swing low", "短期相对强弱转负"],
            risks=["缺少中长期安全边际", "仓位应控制在观察级别"],
        )
    if short == ShortTermLabel.WAIT_BREAKOUT:
        return Decision(
            action=ActionDecision.WAIT,
            summary="方向未确认，等待突破或回踩确认。",
            trigger_conditions=["放量突破压力位", "回踩支撑后重新转强"],
            invalidation_conditions=["横盘后向下破位", "行业相对强弱恶化"],
            risks=["震荡区间内容易出现假突破", "短线交易成本会侵蚀收益"],
        )
    return Decision(
        action=ActionDecision.AVOID,
        summary="中长期或短期条件不足，当前回避。",
        trigger_conditions=["评分重新回到中性以上", "趋势重新站回关键均线"],
        invalidation_conditions=["继续放量下跌", "基本面或行业景气度继续恶化"],
        risks=["弱势股票的反弹持续性较差", "当前不具备清晰风险回报"],
    )
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
cd apps/api
pytest tests/test_scoring.py -v
```

Expected: PASS with 6 tests.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/stock_scorer/scoring.py apps/api/tests/test_scoring.py
git commit -m "feat: add deterministic scoring rules"
```

## Task 4: Fixture Data and Score Assembly

**Files:**
- Create: `apps/api/fixtures/stocks.json`
- Create: `apps/api/src/stock_scorer/fixtures.py`
- Modify: `apps/api/tests/test_scoring.py`

- [ ] **Step 1: Add response assembly tests**

Append to `apps/api/tests/test_scoring.py`:

```python
from stock_scorer.fixtures import get_stock_score


def test_get_stock_score_for_msft():
    score = get_stock_score("MSFT")

    assert score.ticker == "MSFT"
    assert score.medium_term_score == 82
    assert score.short_term_score == 58
    assert score.decision.action == ActionDecision.WAIT
    assert len(score.factors) == 5


def test_get_stock_score_rejects_unknown_ticker():
    try:
        get_stock_score("UNKNOWN")
    except KeyError as exc:
        assert "UNKNOWN" in str(exc)
    else:
        raise AssertionError("Expected KeyError for unknown ticker")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd apps/api
pytest tests/test_scoring.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'stock_scorer.fixtures'`.

- [ ] **Step 3: Create fixture data**

Create `apps/api/fixtures/stocks.json`:

```json
{
  "MSFT": {
    "ticker": "MSFT",
    "company_name": "Microsoft Corporation",
    "last_price": 425.52,
    "medium_term_score": 82,
    "short_term_score": 58,
    "overheated": true,
    "broken_trend": false,
    "data_as_of": "2026-05-20",
    "factors": [
      {"name": "质量/盈利", "score": 90, "evidence": ["ROIC 和自由现金流质量强", "经营利润率处于行业高位"]},
      {"name": "估值", "score": 62, "evidence": ["估值高于市场中位数", "现金流质量部分支撑溢价"]},
      {"name": "成长与预期", "score": 84, "evidence": ["收入和 EPS 增长稳定", "云业务仍是主要增长来源"]},
      {"name": "投资纪律/财务稳健", "score": 86, "evidence": ["资产负债表稳健", "股本稀释风险较低"]},
      {"name": "中期动量与风险", "score": 78, "evidence": ["相对 QQQ 保持强势", "短期涨幅后波动略高"]}
    ]
  }
}
```

- [ ] **Step 4: Implement fixture loader**

Create `apps/api/src/stock_scorer/fixtures.py`:

```python
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from stock_scorer.models import FactorScore, StockScoreResponse
from stock_scorer.scoring import classify_medium_term_score, classify_short_term_state, decide_action


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "stocks.json"


@lru_cache(maxsize=1)
def load_fixture_data() -> dict[str, Any]:
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_stock_score(ticker: str) -> StockScoreResponse:
    normalized = ticker.upper()
    data = load_fixture_data()
    if normalized not in data:
        raise KeyError(f"Ticker not found in fixture data: {normalized}")

    row = data[normalized]
    medium_label = classify_medium_term_score(row["medium_term_score"])
    short_label = classify_short_term_state(
        score=row["short_term_score"],
        overheated=row["overheated"],
        broken_trend=row["broken_trend"],
    )
    decision = decide_action(medium_label, short_label)

    return StockScoreResponse(
        ticker=row["ticker"],
        company_name=row["company_name"],
        last_price=row["last_price"],
        medium_term_score=row["medium_term_score"],
        medium_term_label=medium_label,
        short_term_score=row["short_term_score"],
        short_term_label=short_label,
        factors=[FactorScore(**factor) for factor in row["factors"]],
        decision=decision,
        data_as_of=row["data_as_of"],
    )
```

- [ ] **Step 5: Run tests and verify they pass**

Run:

```bash
cd apps/api
pytest tests/test_scoring.py -v
```

Expected: PASS with 8 tests.

- [ ] **Step 6: Commit**

```bash
git add apps/api/fixtures/stocks.json apps/api/src/stock_scorer/fixtures.py apps/api/tests/test_scoring.py
git commit -m "feat: assemble stock scores from fixtures"
```

## Task 5: FastAPI Endpoint

**Files:**
- Create: `apps/api/src/stock_scorer/app.py`
- Create: `apps/api/tests/test_api.py`

- [ ] **Step 1: Write API tests**

Create `apps/api/tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from stock_scorer.app import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_stock_score_endpoint():
    response = client.get("/v1/stocks/MSFT/score")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "MSFT"
    assert payload["medium_term_score"] == 82
    assert payload["short_term_label"] == "wait_pullback"
    assert payload["decision"]["action"] == "wait"


def test_unknown_stock_score_endpoint_returns_404():
    response = client.get("/v1/stocks/UNKNOWN/score")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticker not found: UNKNOWN"
```

- [ ] **Step 2: Run API tests and verify they fail**

Run:

```bash
cd apps/api
pytest tests/test_api.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'stock_scorer.app'`.

- [ ] **Step 3: Implement FastAPI app**

Create `apps/api/src/stock_scorer/app.py`:

```python
from fastapi import FastAPI, HTTPException

from stock_scorer.fixtures import get_stock_score
from stock_scorer.models import StockScoreResponse


app = FastAPI(title="US Stock Scorer API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/stocks/{ticker}/score", response_model=StockScoreResponse)
def stock_score(ticker: str) -> StockScoreResponse:
    normalized = ticker.upper()
    try:
        return get_stock_score(normalized)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Ticker not found: {normalized}") from exc
```

- [ ] **Step 4: Run all backend tests**

Run:

```bash
cd apps/api
pytest -v
```

Expected: PASS with 11 tests.

- [ ] **Step 5: Run the API locally**

Run:

```bash
cd apps/api
uvicorn stock_scorer.app:app --reload --port 8000
```

Expected: server starts and `http://127.0.0.1:8000/health` returns `{"status":"ok"}`.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/stock_scorer/app.py apps/api/tests/test_api.py
git commit -m "feat: expose stock scoring API"
```

## Task 6: Mini Program Shell

**Files:**
- Create: `apps/miniprogram/project.config.json`
- Create: `apps/miniprogram/app.js`
- Create: `apps/miniprogram/app.json`
- Create: `apps/miniprogram/app.wxss`
- Create: `apps/miniprogram/pages/index/index.json`
- Create: `apps/miniprogram/pages/index/index.wxml`
- Create: `apps/miniprogram/pages/index/index.wxss`
- Create: `apps/miniprogram/pages/index/index.js`

- [ ] **Step 1: Create WeChat project config**

Create `apps/miniprogram/project.config.json`:

```json
{
  "miniprogramRoot": "./",
  "projectname": "us-stock-scorer",
  "description": "Dual-horizon US stock scorer",
  "appid": "touristappid",
  "setting": {
    "urlCheck": false,
    "es6": true,
    "postcss": true,
    "minified": false
  },
  "compileType": "miniprogram"
}
```

- [ ] **Step 2: Create app files**

Create `apps/miniprogram/app.js`:

```javascript
App({
  globalData: {
    apiBaseUrl: "http://127.0.0.1:8000"
  }
});
```

Create `apps/miniprogram/app.json`:

```json
{
  "pages": ["pages/index/index"],
  "window": {
    "navigationBarTitleText": "美股评分器",
    "navigationBarBackgroundColor": "#0f172a",
    "navigationBarTextStyle": "white",
    "backgroundColor": "#f8fafc"
  }
}
```

Create `apps/miniprogram/app.wxss`:

```css
page {
  background: #f8fafc;
  color: #111827;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
```

- [ ] **Step 3: Create page config**

Create `apps/miniprogram/pages/index/index.json`:

```json
{
  "navigationBarTitleText": "美股评分器"
}
```

- [ ] **Step 4: Create page logic**

Create `apps/miniprogram/pages/index/index.js`:

```javascript
const app = getApp();

Page({
  data: {
    ticker: "MSFT",
    loading: false,
    error: "",
    score: null
  },

  onTickerInput(event) {
    this.setData({ ticker: event.detail.value.toUpperCase(), error: "" });
  },

  fetchScore() {
    const ticker = this.data.ticker.trim().toUpperCase();
    if (!ticker) {
      this.setData({ error: "请输入股票代码" });
      return;
    }

    this.setData({ loading: true, error: "" });
    wx.request({
      url: `${app.globalData.apiBaseUrl}/v1/stocks/${ticker}/score`,
      method: "GET",
      success: (response) => {
        if (response.statusCode === 200) {
          this.setData({ score: response.data, error: "" });
          return;
        }
        this.setData({ score: null, error: "没有找到这只股票的数据" });
      },
      fail: () => {
        this.setData({ score: null, error: "无法连接本地后端服务" });
      },
      complete: () => {
        this.setData({ loading: false });
      }
    });
  },

  onLoad() {
    this.fetchScore();
  }
});
```

- [ ] **Step 5: Create page markup**

Create `apps/miniprogram/pages/index/index.wxml`:

```xml
<view class="page">
  <view class="toolbar">
    <input class="ticker-input" value="{{ticker}}" bindinput="onTickerInput" placeholder="输入美股代码" />
    <button class="query-button" bindtap="fetchScore" loading="{{loading}}">查询</button>
  </view>

  <view wx:if="{{error}}" class="error">{{error}}</view>

  <view wx:if="{{score}}" class="summary">
    <view class="ticker-row">
      <text class="ticker">{{score.ticker}}</text>
      <text class="company">{{score.company_name}}</text>
    </view>
    <text class="price">最新价：${{score.last_price}}</text>
    <view class="score-grid">
      <view class="score-box">
        <text class="score-label">中长期</text>
        <text class="score-value">{{score.medium_term_score}}</text>
      </view>
      <view class="score-box">
        <text class="score-label">1-2周</text>
        <text class="score-value">{{score.short_term_score}}</text>
      </view>
    </view>
    <view class="decision">
      <text class="decision-title">当前行动</text>
      <text class="decision-copy">{{score.decision.summary}}</text>
    </view>
  </view>

  <view wx:if="{{score}}" class="section">
    <text class="section-title">因子证据</text>
    <view wx:for="{{score.factors}}" wx:key="name" class="factor">
      <view class="factor-head">
        <text>{{item.name}}</text>
        <text>{{item.score}}</text>
      </view>
      <text wx:for="{{item.evidence}}" wx:key="*this" class="evidence">- {{item}}</text>
    </view>
  </view>

  <view wx:if="{{score}}" class="section">
    <text class="section-title">触发条件</text>
    <text wx:for="{{score.decision.trigger_conditions}}" wx:key="*this" class="line">- {{item}}</text>
  </view>

  <view wx:if="{{score}}" class="section">
    <text class="section-title">失效条件</text>
    <text wx:for="{{score.decision.invalidation_conditions}}" wx:key="*this" class="line">- {{item}}</text>
  </view>

  <view wx:if="{{score}}" class="section">
    <text class="section-title">风险提示</text>
    <text wx:for="{{score.decision.risks}}" wx:key="*this" class="line">- {{item}}</text>
  </view>
</view>
```

- [ ] **Step 6: Create page styles**

Create `apps/miniprogram/pages/index/index.wxss`:

```css
.page {
  padding: 24rpx;
}

.toolbar {
  display: flex;
  gap: 16rpx;
  align-items: center;
  margin-bottom: 20rpx;
}

.ticker-input {
  flex: 1;
  height: 80rpx;
  padding: 0 20rpx;
  background: #ffffff;
  border: 1rpx solid #cbd5e1;
  border-radius: 8rpx;
}

.query-button {
  width: 160rpx;
  height: 80rpx;
  line-height: 80rpx;
  background: #2563eb;
  color: #ffffff;
  border-radius: 8rpx;
  font-size: 28rpx;
}

.error {
  padding: 20rpx;
  background: #fee2e2;
  color: #991b1b;
  border-radius: 8rpx;
}

.summary,
.section {
  padding: 24rpx;
  margin-bottom: 20rpx;
  background: #ffffff;
  border: 1rpx solid #e2e8f0;
  border-radius: 8rpx;
}

.ticker-row {
  display: flex;
  gap: 16rpx;
  align-items: baseline;
}

.ticker {
  font-size: 44rpx;
  font-weight: 700;
}

.company,
.price,
.decision-copy,
.line,
.evidence {
  display: block;
  color: #475569;
  font-size: 26rpx;
  line-height: 1.6;
}

.score-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
  margin: 24rpx 0;
}

.score-box {
  padding: 20rpx;
  background: #f8fafc;
  border-radius: 8rpx;
}

.score-label {
  display: block;
  color: #64748b;
  font-size: 24rpx;
}

.score-value {
  display: block;
  color: #0f172a;
  font-size: 48rpx;
  font-weight: 700;
}

.decision-title,
.section-title {
  display: block;
  margin-bottom: 12rpx;
  color: #0f172a;
  font-size: 30rpx;
  font-weight: 700;
}

.factor {
  padding: 16rpx 0;
  border-top: 1rpx solid #e2e8f0;
}

.factor:first-of-type {
  border-top: 0;
}

.factor-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8rpx;
  color: #111827;
  font-size: 28rpx;
  font-weight: 600;
}
```

- [ ] **Step 7: Open the mini program in WeChat DevTools**

Open `apps/miniprogram` in WeChat DevTools. With the backend running on port 8000 and URL checks disabled for local development, the first page should load MSFT fixture data.

- [ ] **Step 8: Commit**

```bash
git add apps/miniprogram
git commit -m "feat: add mini program scoring UI"
```

## Task 7: Research and Shared Documentation

**Files:**
- Create: `apps/research/README.md`
- Create: `packages/shared/README.md`
- Modify: `README.md`

- [ ] **Step 1: Create research README**

Create `apps/research/README.md`:

```markdown
# Research

This folder is for local experiments before production code changes.

Initial research sequence:

1. Build a 20-50 ticker watchlist.
2. Compare fixture output against manual judgment.
3. Add real data ingestion in a separate task.
4. Store daily score snapshots before doing 5-year backtests.
```

- [ ] **Step 2: Create shared package README**

Create `packages/shared/README.md`:

```markdown
# Shared

This folder stores shared schema notes and enum mapping between the FastAPI backend and the WeChat Mini Program.

The backend remains the source of truth for scoring logic. The mini program should only render API responses.
```

- [ ] **Step 3: Update root README run commands**

Append to `README.md`:

````markdown

## Local Development

Backend:

```bash
cd apps/api
python -m pip install -e ".[dev]"
uvicorn stock_scorer.app:app --reload --port 8000
```

Tests:

```bash
cd apps/api
pytest -v
```

Mini Program:

Open `apps/miniprogram` in WeChat DevTools.
````

- [ ] **Step 4: Commit**

```bash
git add README.md apps/research/README.md packages/shared/README.md
git commit -m "docs: document local development workflow"
```

## Task 8: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run backend tests**

Run:

```bash
cd apps/api
pytest -v
```

Expected: PASS with 11 tests.

- [ ] **Step 2: Run API smoke check**

Run:

```bash
cd apps/api
uvicorn stock_scorer.app:app --port 8000
```

In another terminal:

```bash
curl http://127.0.0.1:8000/v1/stocks/MSFT/score
```

Expected: JSON response contains `"ticker":"MSFT"`, `"medium_term_score":82`, and `"decision":{"action":"wait"`.

- [ ] **Step 3: Verify git status**

Run:

```bash
git status --short
```

Expected: no uncommitted changes.
