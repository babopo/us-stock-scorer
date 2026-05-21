export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE" | "PATCH";

export type HeaderMap = Record<string, string>;

export type QueryValue = string | number | boolean | null | undefined;

export type QueryParams = Record<string, QueryValue>;

export interface ApiRequest {
  method: HttpMethod;
  url: string;
  headers?: HeaderMap;
  query?: QueryParams;
  body?: unknown;
  timeoutMs?: number;
}

export interface ApiResponse<T = unknown> {
  status: number;
  headers?: HeaderMap;
  data: T;
}

export type ApiTransport = <T = unknown>(request: ApiRequest) => Promise<ApiResponse<T>>;

export type ApiErrorCode =
  | "bad_request"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "rate_limited"
  | "upstream_error"
  | "service_unavailable"
  | "internal_error"
  | "request_failed";

export interface ApiErrorOptions {
  status: number;
  code: ApiErrorCode;
  detail: unknown;
  requestId?: string;
  message?: string;
}

export type HorizonLabel = "strong" | "positive" | "neutral" | "weak" | "avoid";

export type ShortTermLabel = "entry" | "probe" | "wait_pullback" | "wait_breakout" | "avoid";

export type ActionDecision = "buy_in_tranches" | "small_probe" | "wait" | "short_term_only" | "avoid";

export interface FactorScore {
  name: string;
  score: number;
  evidence: string[];
}

export interface Decision {
  action: ActionDecision;
  summary: string;
  trigger_conditions: string[];
  invalidation_conditions: string[];
  risks: string[];
}

export interface StockScoreResponse {
  ticker: string;
  company_name: string;
  last_price: number;
  medium_term_score: number;
  medium_term_label: HorizonLabel;
  short_term_score: number;
  short_term_label: ShortTermLabel;
  factors: FactorScore[];
  decision: Decision;
  data_as_of: string;
  data_source: string;
}

export interface HealthResponse {
  status: string;
}

export type ProviderStatus = Record<string, unknown>;

export type TickerRawData = Record<string, unknown>;

export type ScoreSnapshots = Record<string, unknown>;

export type RefreshTickerResponse = Record<string, unknown>;

export interface StockScorerClientOptions {
  baseUrl?: string;
  transport: ApiTransport;
  headers?: HeaderMap;
  timeoutMs?: number;
}

export interface ScoreSnapshotOptions {
  date?: string;
}

export interface StockScorerClient {
  getHealth(): Promise<HealthResponse>;
  getStockScore(ticker: string): Promise<StockScoreResponse>;
  getProviderStatus(): Promise<ProviderStatus>;
  getTickerRawData(ticker: string): Promise<TickerRawData>;
  getScoreSnapshots(ticker: string, options?: ScoreSnapshotOptions): Promise<ScoreSnapshots>;
  refreshTicker(ticker: string): Promise<RefreshTickerResponse>;
}
