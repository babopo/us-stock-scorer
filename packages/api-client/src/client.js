const { createApiError } = require("./errors");
const { joinUrl } = require("./url");

const DEFAULT_TIMEOUT_MS = 15000;

function createStockScorerClient(options) {
  const { baseUrl = "", transport, headers = {}, timeoutMs = DEFAULT_TIMEOUT_MS } = options || {};

  if (typeof transport !== "function") {
    throw new TypeError("createStockScorerClient requires a transport function");
  }

  async function request(method, path, requestOptions) {
    const response = normalizeResponse(
      await transport({
        method,
        url: joinUrl(baseUrl, path),
        query: requestOptions && requestOptions.query,
        body: requestOptions && requestOptions.body,
        headers,
        timeoutMs
      })
    );

    if (response.status < 200 || response.status >= 300) {
      throw createApiError(response);
    }

    return response.data;
  }

  return {
    getHealth() {
      return request("GET", "/health");
    },

    getStockScore(ticker) {
      const normalizedTicker = normalizeTicker(ticker);
      return request("GET", `/v1/stocks/${encodeURIComponent(normalizedTicker)}/score`);
    },

    getProviderStatus() {
      return request("GET", "/v1/admin/providers/status");
    },

    getTickerRawData(ticker) {
      const normalizedTicker = normalizeTicker(ticker);
      return request("GET", `/v1/admin/stocks/${encodeURIComponent(normalizedTicker)}/raw-data`);
    },

    getScoreSnapshots(ticker, options) {
      const normalizedTicker = normalizeTicker(ticker);
      return request("GET", `/v1/admin/stocks/${encodeURIComponent(normalizedTicker)}/snapshots`, {
        query: {
          date: options && options.date
        }
      });
    },

    refreshTicker(ticker) {
      const normalizedTicker = normalizeTicker(ticker);
      return request("POST", `/v1/admin/stocks/${encodeURIComponent(normalizedTicker)}/refresh`);
    }
  };
}

function normalizeTicker(ticker) {
  const normalized = String(ticker || "").trim().toUpperCase();
  if (!normalized) {
    throw new TypeError("ticker is required");
  }
  return normalized;
}

function normalizeResponse(response) {
  if (!response || typeof response !== "object") {
    throw new TypeError("transport returned an empty response");
  }

  const status = response.status || response.statusCode;
  if (typeof status !== "number") {
    throw new TypeError("transport response must include status");
  }

  return {
    status,
    headers: response.headers || response.header || {},
    data: response.data
  };
}

module.exports = {
  createStockScorerClient,
  normalizeTicker
};
