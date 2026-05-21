import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ApiError,
  type ApiRequest,
  type ApiTransport,
  createStockScorerClient,
  createWxTransport,
  normalizeTicker,
  type StockScoreResponse,
  type WxRequestApi
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

test("createWxTransport adapts wx.request to the shared transport contract", async () => {
  const wxApi: WxRequestApi = {
    request(options) {
      assert.equal(options.url, "http://127.0.0.1:8000/health?debug=true");
      assert.equal(options.method, "GET");
      options.success({
        statusCode: 200,
        header: { "x-request-id": "req_456" },
        data: { status: "ok" } as Parameters<typeof options.success>[0]["data"]
      });
    }
  };

  const transport: ApiTransport = createWxTransport(wxApi);
  const response = await transport({
    method: "GET",
    url: "http://127.0.0.1:8000/health",
    query: { debug: true }
  });

  assert.equal(response.status, 200);
  assert.deepEqual(response.data, { status: "ok" });
});
