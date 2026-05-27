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
    admin/        # React/Vite/Ant Design web admin for scoring, research and ops
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

当前版本已包含：

- FastAPI 后端评分 API，默认使用 fixture 数据，也支持 FMP、Finnhub 和 Alpha Vantage 数据源配置及有序 fallback。
- 共享 TypeScript API client，统一封装 Web `fetch` transport、Bearer token、ticker 规范化、错误映射、回测和策略治理 API。
- React/Vite/Ant Design Web 管理后台，登录后按 `/score`、`/strategy`、`/backtests`、`/operations` 拆分为数据查询、策略管理、回测实验和运维操作工作区；移动端底部导航可用，页面禁止输入框聚焦时自动缩放。
- 管理端 FastAPI 接口：登录/session/logout、数据源状态、原始数据、历史评分快照、单只 ticker 刷新、历史同步、回测运行、策略版本列表、候选策略生成、晋升和归档。
- 研究闭环：SQLite 研究库、历史日线同步、历史评分快照、回测运行记录、保守参数网格演化、Admin 回测/策略面板和 systemd 定时任务。
- 策略审核 UI 会把候选策略与当前 active 策略逐项对比，展示入场门槛、止损风险、目标收益、持仓周期和仓位变化，帮助判断候选策略是否值得晋升。

下一阶段重点是真实数据源的历史覆盖率、更完整的回测报表、候选策略和验证指标的长期表现追踪。
当前服务端已经要求所有 `/v1` 业务接口携带 Bearer token；`/health` 保持公开用于健康检查。

## Local Development

Backend:

```bash
cd apps/api
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn stock_scorer.app:app --reload --port 8000
```

本地 Web 管理后台默认请求 `http://127.0.0.1:8000`。生产构建默认使用同源 API，让 Nginx 代理 `/v1/`、`/health`、`/docs`、`/redoc` 和 `/openapi.json` 到 FastAPI。如果本地端口或域名不同，可以设置：

```bash
export ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

本地启动受保护接口前，至少配置只读 token 和 Admin 登录账号：

```bash
export STOCK_SCORER_READ_TOKEN=local-read-token
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=change-me
export ADMIN_SESSION_TTL_SECONDS=43200
```

调试阶段后端默认只读 token 也是 `local-read-token`；上线前应改成动态登录或至少替换为长随机 token。

`ADMIN_AUTH_TOKEN` 是可选的静态管理员 Bearer token，适合脚本或过渡期运维调用；Web 管理后台会使用用户名密码登录后拿到短期 session token。

默认使用 fixture 数据。接入真实美股数据时，推荐先申请 Financial Modeling Prep API key，然后启动前配置：

```bash
export STOCK_SCORER_DATA_SOURCE=fmp
export FMP_API_KEY=your_api_key
uvicorn stock_scorer.app:app --reload --port 8000
```

当前 FMP 接入会拉取 `quote`、`historical-price-eod/full`、`profile`、`income-statement`、`ratios-ttm` 和 `key-metrics-ttm`，用 EOD 日线、公司 profile、利润率、增长、估值和财务稳健代理生成第一阶段评分。没有 key、触发限流或上游不可用时，API 会返回 503/502，并保留 fixture 作为默认开发模式。

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
```

打开管理后台后使用 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 登录。登录成功后前端把短期 Admin session token 存到 `sessionStorage`，请求管理端接口时自动带 Bearer token。生产环境不要把长期 Admin token 打进前端静态包。

管理后台路由：

- `/score`：数据查询，生成六维评分、交易结论和原始响应。
- `/strategy`：策略管理，生成候选策略、对比 active 策略、晋升或归档候选策略。
- `/backtests`：回测实验，运行回测并查看最近回测记录。
- `/operations`：运维操作，查看数据源状态、原始数据、历史快照和刷新结果。

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

## API Surface

公开健康检查：

- `GET /health`

只读评分接口，需要 `STOCK_SCORER_READ_TOKEN` 或 Admin Bearer token：

- `GET /v1/stocks/{ticker}/score`

Admin 认证：

- `POST /v1/admin/auth/login`
- `GET /v1/admin/auth/session`
- `POST /v1/admin/auth/logout`

Admin 运维和研究接口，需要 Admin Bearer token：

- `GET /v1/admin/providers/status`
- `GET /v1/admin/stocks/{ticker}/raw-data`
- `GET /v1/admin/stocks/{ticker}/snapshots`
- `POST /v1/admin/stocks/{ticker}/refresh`
- `GET /v1/admin/history/syncs`
- `POST /v1/admin/history/sync`
- `GET /v1/admin/backtests/runs`
- `POST /v1/admin/backtests/runs`
- `GET /v1/admin/strategies`
- `POST /v1/admin/strategies/evolve`
- `POST /v1/admin/strategies/{strategy_id}/promote`
- `POST /v1/admin/strategies/{strategy_id}/archive`

## Backtesting and Strategy Evolution

研究库默认写入 `apps/api/data/stock_scorer.sqlite3`，可通过 `STOCK_SCORER_DB_PATH` 覆盖。首次运行会自动建表并创建 `default-v1` active 策略版本。

手动回测：

```bash
cd apps/api
. .venv/bin/activate
stock-scorer backtest run --tickers MSFT,NVDA --start-date 2026-01-01 --end-date 2026-03-31
```

手动生成候选策略：

```bash
stock-scorer evolve run --tickers MSFT,NVDA \
  --training-start-date 2025-09-01 \
  --training-end-date 2026-01-31 \
  --validation-start-date 2026-02-01 \
  --validation-end-date 2026-03-31
```

手动同步历史日线：

```bash
stock-scorer history sync --tickers MSFT,NVDA --end-date 2026-03-31
```

历史日线同步会同时生成历史评分快照。快照包括当日 as-of 价格窗口、provider overview 输入和完整评分结果，可通过 Admin API 查询：

```bash
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  "http://127.0.0.1:8000/v1/admin/stocks/MSFT/snapshots?date=2026-03-31"
```

生产部署会安装并启用 `us-stock-scorer-backtest.timer`，默认在北京时间周二到周六 06:30 运行一次历史日线同步、历史评分快照生成、回测和策略演化。可在 `apps/api/.env` 中设置 `BACKTEST_TICKERS=MSFT,NVDA,AAPL` 覆盖默认标的池；未设置时 systemd 服务使用 `NVDA,AAPL,MSFT,AMZN,GOOGL,META,TSLA,AMD,INTC`。

策略版本字段含义：

- `medium_entry_threshold` / `short_entry_threshold`：中期和短线分数达到多少才允许入场。
- `stop_loss_pct`：触发止损退出的跌幅。
- `take_profit_pct`：触发止盈退出的涨幅。
- `max_holding_days`：最长持仓天数。
- `position_size_pct`：每次入场使用的资金比例。

策略审核不要只看参数大小。候选策略应结合验证回测指标判断：`total_return`、`max_drawdown`、`annualized_return`、`win_rate`、`trade_count`、`average_holding_days` 和 `buy_hold_return`。当前演化目标是偏保守的 `total_return - max_drawdown * 0.5`。

## Production Deployment

当前服务器部署入口是：

```bash
cd /home/admin/us-stock-scorer
sudo -n env SERVER_NAME=us-stock-scorer.local bash deploy/install-production.sh
```

脚本会按顺序构建 `@stock-scorer/api-client`、构建 `@stock-scorer/admin`、把前端产物发布到 `/var/www/us-stock-scorer/admin`、安装 FastAPI 包、刷新 systemd unit 和 Nginx 配置，然后重载服务。

常用部署后验证：

```bash
sudo -n nginx -t
systemctl is-active us-stock-scorer-api.service
curl -fsS http://127.0.0.1:8000/health
curl -fsS -H "Host: us-stock-scorer.local" http://127.0.0.1/health
curl -fsSI -H "Host: us-stock-scorer.local" http://127.0.0.1/
```
