const test = require("node:test");
const assert = require("node:assert/strict");

const {
  ApiError,
  createStockScorerClient,
  createWxTransport,
  normalizeTicker
} = require("../src");

test("normalizeTicker trims and uppercases ticker symbols", () => {
  assert.equal(normalizeTicker(" msft "), "MSFT");
  assert.throws(() => normalizeTicker(""), /ticker is required/);
});

test("getStockScore calls the normalized score endpoint", async () => {
  const requests = [];
  const client = createStockScorerClient({
    baseUrl: "http://127.0.0.1:8000/",
    transport: async (request) => {
      requests.push(request);
      return {
        status: 200,
        headers: {},
        data: { ticker: "MSFT" }
      };
    }
  });

  const score = await client.getStockScore(" msft ");

  assert.deepEqual(score, { ticker: "MSFT" });
  assert.equal(requests[0].method, "GET");
  assert.equal(requests[0].url, "http://127.0.0.1:8000/v1/stocks/MSFT/score");
});

test("non-2xx responses are mapped to ApiError", async () => {
  const client = createStockScorerClient({
    transport: async () => ({
      status: 404,
      headers: { "x-request-id": "req_123" },
      data: { detail: "Ticker not found: UNKNOWN" }
    })
  });

  await assert.rejects(
    () => client.getStockScore("UNKNOWN"),
    (error) => {
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
  const wxApi = {
    request(options) {
      assert.equal(options.url, "http://127.0.0.1:8000/health?debug=true");
      assert.equal(options.method, "GET");
      options.success({
        statusCode: 200,
        header: { "x-request-id": "req_456" },
        data: { status: "ok" }
      });
    }
  };

  const transport = createWxTransport(wxApi);
  const response = await transport({
    method: "GET",
    url: "http://127.0.0.1:8000/health",
    query: { debug: true }
  });

  assert.equal(response.status, 200);
  assert.deepEqual(response.data, { status: "ok" });
});
