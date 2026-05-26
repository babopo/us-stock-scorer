import { createApiError } from "./errors";
import type {
  AdminLoginResponse,
  AdminLogoutResponse,
  AdminSessionResponse,
  ApiRequest,
  ApiResponse,
  BacktestRunRequest,
  BacktestRunResponse,
  BacktestRunsResponse,
  EvolutionRunRequest,
  EvolutionRunResponse,
  HeaderMap,
  HistorySyncRequest,
  HistorySyncResponse,
  HistorySyncRunsResponse,
  HttpMethod,
  QueryParams,
  RefreshTickerResponse,
  StockScorerClient,
  StockScorerClientOptions,
  StockScoreResponse,
  StrategyVersionsResponse
} from "./types";
import { joinUrl } from "./url";

const DEFAULT_TIMEOUT_MS = 15000;

interface RequestOptions {
  query?: QueryParams;
  body?: unknown;
}

interface TransportResponse<T> {
  status?: number;
  statusCode?: number;
  headers?: HeaderMap;
  header?: HeaderMap;
  data: T;
}

export function createStockScorerClient(options: StockScorerClientOptions): StockScorerClient {
  const { baseUrl = "", transport, headers = {}, timeoutMs = DEFAULT_TIMEOUT_MS } = options || {};

  if (typeof transport !== "function") {
    throw new TypeError("createStockScorerClient requires a transport function");
  }

  async function request<T>(method: HttpMethod, path: string, requestOptions: RequestOptions = {}): Promise<T> {
    const apiRequest: ApiRequest = {
      method,
      url: joinUrl(baseUrl, path),
      headers,
      timeoutMs
    };

    if (requestOptions.query) {
      apiRequest.query = requestOptions.query;
    }

    if (requestOptions.body !== undefined) {
      apiRequest.body = requestOptions.body;
    }

    const response = normalizeResponse(
      await transport<T>(apiRequest)
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
      return request<StockScoreResponse>("GET", `/v1/stocks/${encodeURIComponent(normalizedTicker)}/score`);
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
      return request<RefreshTickerResponse>("POST", `/v1/admin/stocks/${encodeURIComponent(normalizedTicker)}/refresh`);
    },

    loginAdmin(username, password) {
      return request<AdminLoginResponse>("POST", "/v1/admin/auth/login", {
        body: {
          username,
          password
        }
      });
    },

    getAdminSession() {
      return request<AdminSessionResponse>("GET", "/v1/admin/auth/session");
    },

    logoutAdmin() {
      return request<AdminLogoutResponse>("POST", "/v1/admin/auth/logout");
    },

    getBacktestRuns() {
      return request<BacktestRunsResponse>("GET", "/v1/admin/backtests/runs");
    },

    runBacktest(backtestRequest: BacktestRunRequest) {
      return request<BacktestRunResponse>("POST", "/v1/admin/backtests/runs", {
        body: backtestRequest
      });
    },

    getStrategyVersions() {
      return request<StrategyVersionsResponse>("GET", "/v1/admin/strategies");
    },

    evolveStrategy(evolutionRequest: EvolutionRunRequest) {
      return request<EvolutionRunResponse>("POST", "/v1/admin/strategies/evolve", {
        body: evolutionRequest
      });
    },

    getHistorySyncRuns() {
      return request<HistorySyncRunsResponse>("GET", "/v1/admin/history/syncs");
    },

    syncHistory(historyRequest: HistorySyncRequest) {
      return request<HistorySyncResponse>("POST", "/v1/admin/history/sync", {
        body: historyRequest
      });
    }
  };
}

export function normalizeTicker(ticker: string): string {
  const normalized = String(ticker || "").trim().toUpperCase();
  if (!normalized) {
    throw new TypeError("ticker is required");
  }
  return normalized;
}

export function normalizeResponse<T>(response: TransportResponse<T> | null | undefined): ApiResponse<T> & { headers: HeaderMap } {
  if (!response || typeof response !== "object") {
    throw new TypeError("transport returned an empty response");
  }

  const status = response.status ?? response.statusCode;
  if (typeof status !== "number") {
    throw new TypeError("transport response must include status");
  }

  return {
    status,
    headers: response.headers || response.header || {},
    data: response.data
  };
}
