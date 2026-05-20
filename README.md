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
