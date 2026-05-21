# US Stock Scorer

个人使用的双周期美股买入时机评分器。

目标是输入一个美股 ticker，同时输出：

- 中长期判断：未来 3-12 个月是否值得持有或分批建仓。
- 短期判断：未来 1-2 周，也就是 5-10 个交易日内是否适合入场。
- 当前行动建议：可分批买入、可小仓试探、观察等待、只适合短线或回避。

## Monorepo Layout

```text
us-stock-scorer/
  apps/
    api/          # FastAPI backend, scoring engine, tests
    miniprogram/  # 微信小程序前端
    research/     # 本地研究脚本和回测实验
  packages/
    shared/       # 前后端共享说明、枚举或 schema 文档
  docs/
    superpowers/
      specs/      # 设计文档
      plans/      # 实施计划
```

## Current Status

当前 MVP 包含基于 fixture 数据的后端评分 API 和微信小程序页面。下一阶段是接入真实行情/财报数据，并保存每日评分快照用于回测。

## Local Development

Backend:

```bash
cd apps/api
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn stock_scorer.app:app --reload --port 8000
```

默认使用 fixture 数据。接入真实美股数据时，推荐先申请 Financial Modeling Prep API key，然后启动前配置：

```bash
export STOCK_SCORER_DATA_SOURCE=fmp
export FMP_API_KEY=your_api_key
uvicorn stock_scorer.app:app --reload --port 8000
```

当前 FMP 接入会拉取 `quote`、`historical-price-eod/full`、`profile` 和 `income-statement`，用 EOD 日线、公司 profile、利润率和增长代理生成第一阶段评分。没有 key、触发限流或上游不可用时，API 会返回 503/502，并保留 fixture 作为默认开发模式。

Alpha Vantage 仍作为备用数据源保留：

```bash
export STOCK_SCORER_DATA_SOURCE=alpha_vantage
export ALPHA_VANTAGE_API_KEY=your_api_key
```

Tests:

```bash
cd apps/api
. .venv/bin/activate
pytest -v
```

Mini Program:

Open `apps/miniprogram` in WeChat DevTools.
