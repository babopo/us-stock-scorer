# Web 管理后台与统一 API Client 设计

日期：2026-05-22

## 当前实现状态

截至 2026-05-22，仓库已经完成第一版 Web 管理后台和统一 API client 的主要骨架：

- `packages/api-client` 已提供 TypeScript client、`fetch` transport、`wx.request` transport、ticker 规范化和错误映射。
- `apps/miniprogram` 已迁移到 TypeScript，并通过共享 client 调用后端评分接口。
- `apps/admin` 已使用 Vite、React、TypeScript 和 TanStack Query 建立本地后台，首屏包含评分调试、数据源状态和运维操作区域。
- `apps/api` 已增加 CORS 配置和第一批管理端接口：provider status、fixture raw data、ticker refresh。
- 根目录 `pnpm build`、`pnpm typecheck`、`pnpm test` 已纳入 `apps/admin`。

仍未完成的部分：

- 管理端 token 校验尚未在 FastAPI 中强制执行。
- OpenAPI 类型生成脚本还未接入，当前 client 类型仍为手写维护。
- `/v1/admin/stocks/{ticker}/snapshots`、jobs 查询、批量刷新和评分快照落库尚未实现。
- 真实数据源的 raw-data 排查接口尚未开放，目前 raw-data 只支持 fixture 数据源。
- 服务器部署、反向代理和生产鉴权文档仍待补充。

## 背景

当前 monorepo 已有：

- `apps/api`：FastAPI 后端，提供评分接口和行情数据源封装。
- `apps/miniprogram`：微信小程序，通过共享 API client 和 `wx.request` transport 调用后端。
- `apps/admin`：React/Vite Web 管理后台，用于本地调试评分、数据源状态和管理端接口。
- `packages/api-client`：前端共享 API client、类型、错误映射和 transport 适配。
- `packages/shared`：共享 schema / enum 说明占位。

增加 Web 管理后台后，小程序和后台不能各自手写接口路径、错误处理、鉴权和返回值解析。否则后端接口稍有调整，两端都要改一遍，且行为容易不一致。

## 目标

1. 在 monorepo 中增加一个 Web 管理后台，优先服务个人开发、调试和轻量运维。
2. 将前端接口调用方式统一收敛到共享 client，避免小程序和管理后台重复拼 URL、重复处理错误、重复维护类型。
3. 后端继续作为业务逻辑和 OpenAPI 合约的唯一源头。
4. 为后续部署到服务器开发预留配置、鉴权、CORS、反向代理和环境隔离方案。

## 非目标

- 第一版不做复杂权限系统、团队协作后台或多租户。
- 第一版不做完整数据治理平台。
- 第一版不把管理后台暴露为公开产品页面。
- 第一版不重写现有评分逻辑。

## 推荐架构

```text
apps/api
  FastAPI / Pydantic
  OpenAPI schema source of truth
        |
        | export / generate
        v
packages/api-client
  generated OpenAPI types
  domain client methods
  transport adapters
        |
        +--> apps/miniprogram
        |      wx.request transport
        |
        +--> apps/admin
               fetch transport
```

核心原则：

- 后端接口定义只在 FastAPI / Pydantic 里维护。
- `packages/api-client` 是唯一允许前端直接知道 API path 的地方。
- 小程序和 Web 后台只调用 `client.getStockScore(ticker)` 这类业务方法。
- 平台差异只在 transport 层处理：Web 用 `fetch`，微信小程序用 `wx.request`。

## 目录设计

```text
us-stock-scorer/
  apps/
    api/
      src/stock_scorer/
        app.py
        models.py
        admin_models.py
        admin_routes.py
      tests/
    miniprogram/
      utils/
        api.js
        config.js
    admin/
      index.html
      package.json
      src/
        app/
        pages/
        features/
        api/
  packages/
    api-client/
      package.json
      src/
        generated/
          schema.ts
        client.ts
        errors.ts
        transports/
          fetch.ts
          wx.ts
        index.ts
      test/
    shared/
      README.md
```

`packages/shared` 可以继续保留说明文档，但真正可复用的接口调用代码建议放到 `packages/api-client`，名字更明确。

## API Client 设计

### Client 对外形态

小程序和 Web 后台都只面向同一个 client。当前已实现 `getHealth()`、`getStockScore()`、`getProviderStatus()`、`getTickerRawData()`、`getScoreSnapshots()` 和 `refreshTicker()` 方法，其中 `getScoreSnapshots()` 的后端接口仍待实现。

```ts
const client = createStockScorerClient({
  baseUrl: config.apiBaseUrl,
  transport
});

const score = await client.getStockScore("MSFT");
const health = await client.getHealth();
```

client 方法清单：

- `getHealth()`
- `getStockScore(ticker)`
- `getProviderStatus()`
- `getTickerRawData(ticker)`
- `getScoreSnapshot(ticker, date?)`
- `refreshTicker(ticker)`

其中前两个是消费端可用接口，其余方法是管理后台优先使用的运维接口。

### Transport 接口

`api-client` 内部定义平台无关 request 形态：

```ts
type ApiTransport = <T>(request: ApiRequest) => Promise<ApiResponse<T>>;

type ApiRequest = {
  method: "GET" | "POST" | "PUT" | "DELETE";
  url: string;
  headers?: Record<string, string>;
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  timeoutMs?: number;
};
```

Web 后台使用 `createFetchTransport()`，小程序使用 `createWxTransport(wx)`。这样后续接口增加鉴权 header、trace id、超时、重试、错误映射时，只改 client 或 transport。

### 错误模型

现有 FastAPI 错误返回是：

```json
{ "detail": "Ticker not found: UNKNOWN" }
```

client 内部统一转换为：

```ts
class ApiError extends Error {
  status: number;
  code: string;
  detail: unknown;
  requestId?: string;
}
```

建议映射：

| HTTP 状态 | code | 前端含义 |
|---:|---|---|
| 400 | `bad_request` | 请求参数错误 |
| 401 | `unauthorized` | 未登录或 token 失效 |
| 403 | `forbidden` | 没有后台权限 |
| 404 | `not_found` | ticker 或资源不存在 |
| 429 | `rate_limited` | 数据源或服务限流 |
| 502 | `upstream_error` | 第三方数据源异常 |
| 503 | `service_unavailable` | 配置缺失、数据源不可用 |
| 500 | `internal_error` | 后端未知错误 |

页面只根据 `ApiError.code` 做展示，不直接解析 FastAPI 的 `detail`。

### 合约生成

后端仍然是源头，建议增加脚本：

```bash
cd apps/api
python -m stock_scorer.export_openapi ../../packages/api-client/src/generated/openapi.json
```

再由 `openapi-typescript` 生成 TypeScript 类型：

```bash
pnpm --filter @stock-scorer/api-client generate
```

推荐策略：

- 类型从 OpenAPI 自动生成。
- 业务方法手写，保持接口好用。
- CI 或本地检查确保 OpenAPI 变化时 client 类型同步更新。

## Web 管理后台设计

### 技术选择

建议使用：

- Vite
- React
- TypeScript
- TanStack Query
- React Router

理由：

- 启动轻，适合个人后台和调试工具。
- TanStack Query 能统一处理加载、错误、重试、缓存和刷新。
- 与共享 TypeScript client 组合自然。

### UI 方向

使用 `ui-ux-pro-max` 检索 “fintech SaaS admin dashboard stock scoring operations React” 后，后台 UI 建议采用 Data-Dense Dashboard / Drill-Down 模式：

- 信息架构偏工作台，不做营销式 landing 或大 hero。
- 首屏直接进入评分调试和数据源状态，优先展示 ticker 输入、关键状态、最近请求、错误信息和原始响应。
- 视觉基调沿用当前小程序的深色金融工具感：`#0F172A` 作为背景，`#F59E0B` / `#FBBF24` 作为评分和重点状态色。
- 字体可使用 Fira Sans + Fira Code；数值、ticker、request id、JSON 使用等宽字体。
- 交互重点是表格行 hover、请求状态、过滤器、刷新按钮、JSON 折叠、错误详情展开。
- 图标统一用 Lucide，不使用 emoji 作为 UI 图标。
- 响应式目标覆盖 375px、768px、1024px、1440px，但后台移动端只保证可排查，不追求高频操作效率。

### 页面结构

```text
apps/admin/src/
  app/
    App.tsx
    router.tsx
    queryClient.ts
  pages/
    ScoreDebuggerPage.tsx
    ProviderStatusPage.tsx
    DataLookupPage.tsx
    SnapshotsPage.tsx
    JobsPage.tsx
  features/
    score/
    providers/
    snapshots/
    jobs/
  api/
    client.ts
```

第一版后台页面当前采用单页工作台结构：

1. 评分调试页
   - 输入 ticker。
   - 展示 `getStockScore` 原始响应、格式化评分、因子证据、触发条件、失效条件。
   - 显示后端返回的评分、标签、行动建议、因子和 `data_as_of`。

2. 数据源状态页
   - 当前 `STOCK_SCORER_DATA_SOURCE`。
   - API key 是否配置，只显示 configured / missing，不显示真实 key。
   - 简单健康检查。

3. 原始数据查询页
   - 当前仅支持 fixture 数据源，返回 fixture 原始 ticker payload。
   - 真实数据源的 quote、profile、income statement、历史价格摘要排查仍待实现。

4. 评分快照页
   - 后续落库后展示每日评分历史。
   - 支持 ticker + date 查询。

5. 任务页
   - 触发单只股票刷新。
   - 后续接入批量刷新、自选列表刷新、任务日志。

## 后端接口分层

建议将接口分成消费端 API 和管理端 API：

```text
GET /health

GET /v1/stocks/{ticker}/score

GET  /v1/admin/providers/status
GET  /v1/admin/stocks/{ticker}/raw-data
GET  /v1/admin/stocks/{ticker}/snapshots
POST /v1/admin/stocks/{ticker}/refresh
GET  /v1/admin/jobs
GET  /v1/admin/jobs/{job_id}
```

约定：

- `/v1/stocks/...` 是小程序和后台都可复用的稳定消费接口。
- `/v1/admin/...` 是管理后台专用接口，可以包含更多排查信息。
- 管理端接口不能返回第三方 API key、完整敏感环境变量或服务端路径。
- 所有新接口继续用 Pydantic response model，保证 OpenAPI 可生成类型。

## 配置与环境

### API

```text
STOCK_SCORER_DATA_SOURCE=fixture|fmp|alpha_vantage
FMP_API_KEY=...
ALPHA_VANTAGE_API_KEY=...
ADMIN_AUTH_TOKEN=...
ALLOWED_ORIGINS=http://localhost:5173,https://admin.example.com
```

### Web Admin

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_ADMIN_AUTH_TOKEN=local-dev-token
```

生产环境不建议把长期 token 固化进前端包。个人开发阶段可以先用反向代理 Basic Auth 或短期 token，后续再升级登录态。

### 小程序

```js
App({
  globalData: {
    apiBaseUrl: config.apiBaseUrl
  }
});
```

建议新增 `apps/miniprogram/utils/config.js` 区分本地、体验版、正式版 API 域名。

## 服务端部署草案

个人服务器开发阶段推荐先用 Docker Compose 或 systemd，前面挂 Caddy / Nginx：

```text
https://stock-scorer.example.com
  /api/*     -> FastAPI:8000
  /admin/*   -> static admin build
```

后端运行：

```bash
uvicorn stock_scorer.app:app --host 127.0.0.1 --port 8000
```

反向代理职责：

- HTTPS 证书。
- 管理后台 Basic Auth 或访问控制。
- `/api` 路径转发。
- 静态资源缓存。
- 请求体大小、超时、访问日志。

FastAPI 侧职责：

- CORS 白名单。
- 管理端 token 校验。
- 请求日志和 request id。
- 上游错误转换。

## 本地开发流程

root 已包含 `pnpm-workspace.yaml`：

```yaml
packages:
  - "apps/admin"
  - "apps/miniprogram"
  - "packages/*"
```

本地启动：

```bash
# terminal 1
cd apps/api
uvicorn stock_scorer.app:app --reload --port 8000

# terminal 2
pnpm --filter @stock-scorer/admin dev
```

小程序仍然用微信开发者工具打开 `apps/miniprogram`，请求代码已经改成共享 client。

## 迁移步骤

### 阶段 1：建立共享 API client

状态：已完成。

1. 新增 root `pnpm-workspace.yaml` 和 `package.json`。
2. 新增 `packages/api-client`。
3. 把现有 `/health`、`/v1/stocks/{ticker}/score` 收敛到 `client.getHealth()` 和 `client.getStockScore()`。
4. 提供 `fetch` 和 `wx` 两个 transport。
5. 给 client 加单元测试，覆盖 URL 拼接、ticker normalize、错误映射。

### 阶段 2：改造小程序调用层

状态：已完成，并已迁移到 TypeScript。

1. 新增 `apps/miniprogram/utils/api.ts`。
2. 页面从直接 `wx.request` 改为调用共享 client。
3. 页面只处理 loading、成功渲染、`ApiError.code` 到中文文案的映射。

### 阶段 3：增加管理后台骨架

状态：已完成第一版。

1. 新增 `apps/admin`。
2. 接入 `packages/api-client` 的 fetch transport。
3. 完成评分调试、数据源状态和操作面板。
4. 本地跑通 API + Admin。

### 阶段 4：增加管理端后端接口

状态：部分完成。

1. 已新增 `admin_models.py`，当前路由仍在 `app.py` 中。
2. 已加 `/v1/admin/providers/status`。
3. 已加 `/v1/admin/stocks/{ticker}/raw-data`，当前只支持 fixture 数据源。
4. 已加 `/v1/admin/stocks/{ticker}/refresh`，当前复用同步评分管线。
5. token 校验仍待实现。

### 阶段 5：服务器部署准备

状态：部分完成。

1. 已有 `.env.example`，仍需补齐 admin 相关配置项。
2. 已增加 CORS 配置。
3. 增加 Dockerfile / compose 或 systemd 文档。
4. 增加 Caddy / Nginx 示例。

## 关键约束

- 前端页面不直接写 API path。
- 新接口先写 Pydantic response model，再暴露路由。
- `api-client` 是唯一处理 baseURL、query、headers、错误、超时的位置。
- 后台展示敏感状态时只展示“是否配置”，不展示 secret 值。
- `/v1` 接口尽量保持向后兼容；破坏性改动通过新字段或新版本处理。

## 待确认

1. Web 管理后台是否只给自己使用，还是未来要给其他人登录。
2. 服务器部署倾向 Docker Compose、systemd，还是平台托管。
3. 管理后台第一版是否需要写入能力，例如手动刷新数据、保存自选列表。
4. 后续是否要加数据库保存评分快照；如果要，需要确认 SQLite、Postgres 或其他存储。
