import type {
  AdminLoginResponse,
  AdminLogoutResponse,
  AdminSessionResponse,
  ApiErrorCode,
  ApiErrorOptions,
  ApiRequest,
  ApiResponse,
  ApiTransport,
  HeaderMap,
  HttpMethod,
  QueryParams,
  RefreshTickerResponse,
  StockScorerClient,
  StockScorerClientOptions,
  StockScoreResponse,
  WxRequestApi
} from "@stock-scorer/api-client";

// Keep runtime code inside the mini program root so WeChat can resolve it without miniprogram_npm.
const DEFAULT_TIMEOUT_MS = 15000;

const ERROR_CODE_BY_STATUS: Partial<Record<number, ApiErrorCode>> = {
  400: "bad_request",
  401: "unauthorized",
  403: "forbidden",
  404: "not_found",
  429: "rate_limited",
  502: "upstream_error",
  503: "service_unavailable"
};

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

interface WxRequestResponse<T> {
  statusCode: number;
  header?: HeaderMap;
  data: T;
}

interface WxRequestOptions<T> {
  url: string;
  method: HttpMethod;
  data?: unknown;
  header?: HeaderMap;
  timeout?: number;
  success(response: WxRequestResponse<T>): void;
  fail(error: unknown): void;
}

class MiniProgramApiError extends Error {
  status: number;
  code: ApiErrorCode;
  detail: unknown;
  requestId?: string;

  constructor({ status, code, detail, requestId, message }: ApiErrorOptions) {
    super(message || getErrorMessage(detail, code));
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    if (requestId) {
      this.requestId = requestId;
    }
    Object.setPrototypeOf(this, new.target.prototype);
  }
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

    const response = normalizeResponse(await transport<T>(apiRequest));

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
    }
  };
}

export function createWxTransport(wxApi: WxRequestApi): ApiTransport {
  if (!wxApi || typeof wxApi.request !== "function") {
    throw new TypeError("createWxTransport requires the wx API object");
  }

  return function wxTransport<T>(request: ApiRequest): Promise<ApiResponse<T>> {
    return new Promise((resolve, reject) => {
      const options: WxRequestOptions<T> = {
        url: appendQuery(request.url, request.query),
        method: request.method,
        success(response) {
          resolve({
            status: response.statusCode,
            headers: response.header || {},
            data: response.data
          });
        },
        fail(error) {
          reject(error);
        }
      };

      if (request.body !== undefined) {
        options.data = request.body;
      }
      if (request.headers) {
        options.header = request.headers;
      }
      if (request.timeoutMs !== undefined) {
        options.timeout = request.timeoutMs;
      }

      wxApi.request(options);
    });
  };
}

export function isApiError(error: unknown): error is MiniProgramApiError {
  return (
    error instanceof MiniProgramApiError ||
    Boolean(
      error &&
        typeof error === "object" &&
        "name" in error &&
        (error as { name?: unknown }).name === "ApiError"
    )
  );
}

function normalizeTicker(ticker: string): string {
  const normalized = String(ticker || "").trim().toUpperCase();
  if (!normalized) {
    throw new TypeError("ticker is required");
  }
  return normalized;
}

function normalizeResponse<T>(response: TransportResponse<T> | null | undefined): ApiResponse<T> & { headers: HeaderMap } {
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

function createApiError(response: ApiResponse<unknown> & { headers: HeaderMap }): MiniProgramApiError {
  const status = response.status;
  const detail = getErrorDetail(response.data);
  const requestId = getHeader(response.headers, "x-request-id");
  return new MiniProgramApiError({
    status,
    detail,
    code: getErrorCode(status),
    ...(requestId ? { requestId } : {})
  });
}

function getErrorCode(status: number): ApiErrorCode {
  return ERROR_CODE_BY_STATUS[status] || (status >= 500 ? "internal_error" : "request_failed");
}

function getErrorDetail(data: unknown): unknown {
  if (data && typeof data === "object" && Object.prototype.hasOwnProperty.call(data, "detail")) {
    return (data as { detail: unknown }).detail;
  }
  return data;
}

function getErrorMessage(detail: unknown, code: ApiErrorCode): string {
  if (typeof detail === "string" && detail) {
    return detail;
  }
  return code || "request_failed";
}

function getHeader(headers: HeaderMap | undefined, name: string): string | undefined {
  if (!headers) {
    return undefined;
  }
  const lowerName = name.toLowerCase();
  const found = Object.keys(headers).find((key) => key.toLowerCase() === lowerName);
  return found ? headers[found] : undefined;
}

function joinUrl(baseUrl: string, path: string): string {
  const cleanBaseUrl = String(baseUrl || "").replace(/\/+$/, "");
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${cleanBaseUrl}${cleanPath}`;
}

function appendQuery(url: string, query?: QueryParams): string {
  const entries = Object.entries(query || {}).filter(([, value]) => value !== undefined && value !== null);
  if (!entries.length) {
    return url;
  }

  const queryString = entries
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join("&");

  return `${url}${url.includes("?") ? "&" : "?"}${queryString}`;
}
