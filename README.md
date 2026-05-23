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
    admin/        # React/Vite web admin for scoring and provider debugging
    miniprogram/  # 微信小程序前端
    research/     # 本地研究脚本和回测实验
  packages/
    api-client/   # 前端共享 API client、错误映射和 transport 适配
    shared/       # 前后端共享说明、枚举或 schema 文档
  docs/
    superpowers/
      specs/      # 设计文档
      plans/      # 实施计划
```

## Current Status

当前 MVP 已包含：

- FastAPI 后端评分 API，默认使用 fixture 数据，也支持 FMP 和 Alpha Vantage 数据源配置。
- 共享 TypeScript API client，统一封装 `fetch` 和微信小程序 `wx.request` transport、ticker 规范化和错误映射。
- 微信小程序页面，用共享 client 查询评分并渲染双周期判断、因子雷达和行动建议。
- React/Vite Web 管理后台，用于本地评分调试、数据源状态检查、fixture 原始数据查看和单只 ticker 刷新。
- 管理端 FastAPI 接口：`/v1/admin/providers/status`、`/v1/admin/stocks/{ticker}/raw-data`、`/v1/admin/stocks/{ticker}/refresh`。

下一阶段重点是管理端鉴权、真实数据源的原始数据排查能力、每日评分快照落库和服务器部署文档。

## Local Development

Backend:

```bash
cd apps/api
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn stock_scorer.app:app --reload --port 8000
```

本地 Web 管理后台默认请求 `http://127.0.0.1:8000`。如果端口或域名不同，可以设置：

```bash
export ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

默认使用 fixture 数据。接入真实美股数据时，推荐先申请 Financial Modeling Prep API key，然后启动前配置：

```bash
export STOCK_SCORER_DATA_SOURCE=fmp
export FMP_API_KEY=your_api_key
uvicorn stock_scorer.app:app --reload --port 8000
```

当前 FMP 接入会拉取 `quote`、`historical-price-eod/full`、`profile` 和 `income-statement`，用 EOD 日线、公司 profile、利润率和增长代理生成第一阶段评分。没有 key、触发限流或上游不可用时，API 会返回 503/502，并保留 fixture 作为默认开发模式。

如果 FMP 免费额度或 ticker 覆盖不足，可以配置有序 fallback 链。`STOCK_SCORER_DATA_SOURCES` 存在时会优先于单一的 `STOCK_SCORER_DATA_SOURCE`：

```bash
export STOCK_SCORER_DATA_SOURCES=fmp,finnhub,alpha_vantage
export FMP_API_KEY=your_fmp_api_key
export FINNHUB_API_KEY=your_finnhub_api_key
export ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key
uvicorn stock_scorer.app:app --reload --port 8000
```

评分会按顺序尝试数据源。例如 FMP 查不到 ticker、触发限流或临时不可用时，会自动尝试 Finnhub；Finnhub 失败后再尝试 Alpha Vantage。当前 Finnhub 接入会拉取 `quote`、`stock/candle`、`stock/profile2` 和 `stock/metric`，并映射成统一的评分输入。

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

Web Admin:

```bash
pnpm install
pnpm --filter @stock-scorer/admin dev
```

可选环境变量：

```bash
export VITE_API_BASE_URL=http://127.0.0.1:8000
export VITE_ADMIN_AUTH_TOKEN=local-dev-token
```

当前后端还没有强制校验 `VITE_ADMIN_AUTH_TOKEN`，该变量用于预留管理端鉴权 header。

Mini Program:

Open `apps/miniprogram` in WeChat DevTools.

小程序源码使用 TypeScript，`project.config.json` 已启用微信开发者工具内置的 TypeScript 编译插件。接口调用依赖共享 API client；首次打开或更新依赖后，在仓库根目录安装前端依赖、编译共享 client，然后在微信开发者工具里执行“工具 -> 构建 npm”：

```bash
pnpm install
pnpm build
```

Shared TypeScript checks and tests:

```bash
pnpm typecheck
pnpm test
```

完整本地验证建议：

```bash
cd apps/api
. .venv/bin/activate
pytest -v

cd ../..
pnpm typecheck
pnpm test
```
