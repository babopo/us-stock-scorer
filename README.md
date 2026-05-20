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

目前仓库只包含设计和实施计划，还没有业务代码。下一步按实施计划从后端评分 MVP 开始。

