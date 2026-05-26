import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ApiError,
  type ApiRequest,
  createStockScorerClient,
  normalizeTicker,
  type StockScoreResponse
} from "../src";

const sampleScore: StockScoreResponse = {
  ticker: "MSFT",
  company_name: "Microsoft Corporation",
  last_price: 420.5,
  medium_term_score: 82,
  medium_term_label: "positive",
  short_term_score: 74,
  short_term_label: "probe",
  factors: [
    {
      name: "质量/盈利",
      score: 90,
      evidence: ["ROIC 强"]
    }
  ],
  decision: {
    action: "small_probe",
    summary: "小仓试探",
    trigger_conditions: ["突破前高"],
    invalidation_conditions: ["跌破支撑"],
    risks: ["估值偏高"]
  },
  data_as_of: "2026-05-22",
  data_source: "fixture"
};

test("normalizeTicker trims and uppercases ticker symbols", () => {
  assert.equal(normalizeTicker(" msft "), "MSFT");
  assert.throws(() => normalizeTicker(""), /ticker is required/);
});

test("getStockScore calls the normalized score endpoint", async () => {
  const requests: ApiRequest[] = [];
  const client = createStockScorerClient({
    baseUrl: "http://127.0.0.1:8000/",
    transport: async <T = unknown>(request: ApiRequest) => {
      requests.push(request);
      return {
        status: 200,
        headers: {},
        data: sampleScore as T
      };
    }
  });

  const score = await client.getStockScore(" msft ");
  const firstRequest = requests[0];

  assert.deepEqual(score, sampleScore);
  assert.ok(firstRequest);
  assert.equal(firstRequest.method, "GET");
  assert.equal(firstRequest.url, "http://127.0.0.1:8000/v1/stocks/MSFT/score");
});

test("non-2xx responses are mapped to ApiError", async () => {
  const client = createStockScorerClient({
    transport: async <T = unknown>() => ({
      status: 404,
      headers: { "x-request-id": "req_123" },
      data: { detail: "Ticker not found: UNKNOWN" } as T
    })
  });

  await assert.rejects(
    () => client.getStockScore("UNKNOWN"),
    (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 404);
      assert.equal(error.code, "not_found");
      assert.equal(error.message, "Ticker not found: UNKNOWN");
      assert.equal(error.requestId, "req_123");
      return true;
    }
  );
});

test("admin auth methods call login, session, and logout endpoints", async () => {
  const requests: ApiRequest[] = [];
  const client = createStockScorerClient({
    baseUrl: "http://127.0.0.1:8000",
    transport: async <T = unknown>(request: ApiRequest) => {
      requests.push(request);
      if (request.url.endsWith("/login")) {
        return {
          status: 200,
          headers: {},
          data: {
            access_token: "admin-session-token",
            token_type: "bearer",
            expires_in_seconds: 43200,
            expires_at: "2026-05-23T12:00:00Z"
          } as T
        };
      }
      if (request.url.endsWith("/session")) {
        return {
          status: 200,
          headers: {},
          data: {
            authenticated: true,
            role: "admin",
            expires_at: "2026-05-23T12:00:00Z"
          } as T
        };
      }
      return {
        status: 200,
        headers: {},
        data: { status: "logged_out" } as T
      };
    }
  });

  const login = await client.loginAdmin("admin", "secret-password");
  const session = await client.getAdminSession();
  const logout = await client.logoutAdmin();

  assert.equal(login.access_token, "admin-session-token");
  assert.equal(session.authenticated, true);
  assert.equal(logout.status, "logged_out");
  assert.equal(requests[0]?.method, "POST");
  assert.equal(requests[0]?.url, "http://127.0.0.1:8000/v1/admin/auth/login");
  assert.deepEqual(requests[0]?.body, { username: "admin", password: "secret-password" });
  assert.equal(requests[1]?.method, "GET");
  assert.equal(requests[1]?.url, "http://127.0.0.1:8000/v1/admin/auth/session");
  assert.equal(requests[2]?.method, "POST");
  assert.equal(requests[2]?.url, "http://127.0.0.1:8000/v1/admin/auth/logout");
});

test("backtest and strategy admin methods call research endpoints", async () => {
  const requests: ApiRequest[] = [];
  const client = createStockScorerClient({
    baseUrl: "http://127.0.0.1:8000",
    transport: async <T = unknown>(request: ApiRequest) => {
      requests.push(request);
      if (request.url.endsWith("/backtests/runs") && request.method === "GET") {
        return { status: 200, headers: {}, data: { runs: [] } as T };
      }
      if (request.url.endsWith("/strategies") && request.method === "GET") {
        return { status: 200, headers: {}, data: { strategies: [] } as T };
      }
      if (request.url.endsWith("/strategies/evolve")) {
        return {
          status: 200,
          headers: {},
          data: {
            candidate_strategy_id: 2,
            training_run_id: 3,
            validation_run_id: 4,
            active_validation_return: 0.04,
            validation_total_return: 0.06,
            max_drawdown: 0.02,
            message: "Candidate strategy generated."
          } as T
        };
      }
      return {
        status: 200,
        headers: {},
        data: {
          run_id: 1,
          strategy_id: 1,
          tickers: ["MSFT"],
          start_date: "2026-01-01",
          end_date: "2026-03-01",
          initial_cash: 10000,
          metrics: {
            total_return: 0.05,
            annualized_return: 0.25,
            max_drawdown: 0.01,
            win_rate: 1,
            trade_count: 1,
            average_holding_days: 12,
            buy_hold_return: 0.04
          },
          trades: []
        } as T
      };
    }
  });

  await client.getBacktestRuns();
  await client.runBacktest({ tickers: ["MSFT"], start_date: "2026-01-01", end_date: "2026-03-01", initial_cash: 10000 });
  await client.getStrategyVersions();
  await client.evolveStrategy({
    tickers: ["MSFT"],
    training_start_date: "2026-01-01",
    training_end_date: "2026-02-01",
    validation_start_date: "2026-02-02",
    validation_end_date: "2026-03-01",
    initial_cash: 10000
  });

  assert.equal(requests[0]?.method, "GET");
  assert.equal(requests[0]?.url, "http://127.0.0.1:8000/v1/admin/backtests/runs");
  assert.equal(requests[1]?.method, "POST");
  assert.equal(requests[1]?.url, "http://127.0.0.1:8000/v1/admin/backtests/runs");
  assert.deepEqual(requests[1]?.body, {
    tickers: ["MSFT"],
    start_date: "2026-01-01",
    end_date: "2026-03-01",
    initial_cash: 10000
  });
  assert.equal(requests[2]?.url, "http://127.0.0.1:8000/v1/admin/strategies");
  assert.equal(requests[3]?.method, "POST");
  assert.equal(requests[3]?.url, "http://127.0.0.1:8000/v1/admin/strategies/evolve");
});

test("history sync admin methods call sync endpoints", async () => {
  const requests: ApiRequest[] = [];
  const client = createStockScorerClient({
    baseUrl: "http://127.0.0.1:8000",
    transport: async <T = unknown>(request: ApiRequest) => {
      requests.push(request);
      if (request.method === "GET") {
        return { status: 200, headers: {}, data: { runs: [] } as T };
      }
      return {
        status: 200,
        headers: {},
        data: {
          run_id: 1,
          tickers: [],
          completed_count: 0,
          failed_count: 0
        } as T
      };
    }
  });

  await client.getHistorySyncRuns();
  await client.syncHistory({ tickers: ["MSFT"], end_date: "2026-01-04" });

  assert.equal(requests[0]?.method, "GET");
  assert.equal(requests[0]?.url, "http://127.0.0.1:8000/v1/admin/history/syncs");
  assert.equal(requests[1]?.method, "POST");
  assert.equal(requests[1]?.url, "http://127.0.0.1:8000/v1/admin/history/sync");
  assert.deepEqual(requests[1]?.body, { tickers: ["MSFT"], end_date: "2026-01-04" });
});

test("getScoreSnapshots calls the score snapshot endpoint with optional date", async () => {
  const requests: ApiRequest[] = [];
  const client = createStockScorerClient({
    baseUrl: "http://127.0.0.1:8000",
    transport: async <T = unknown>(request: ApiRequest) => {
      requests.push(request);
      return { status: 200, headers: {}, data: { ticker: "MSFT", snapshots: [] } as T };
    }
  });

  await client.getScoreSnapshots("msft", { date: "2026-03-31" });

  assert.equal(requests[0]?.method, "GET");
  assert.equal(requests[0]?.url, "http://127.0.0.1:8000/v1/admin/stocks/MSFT/snapshots");
  assert.deepEqual(requests[0]?.query, { date: "2026-03-31" });
});
