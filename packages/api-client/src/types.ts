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

export interface ScoreSnapshot {
  ticker: string;
  date: string;
  source: string;
  medium_term_score: number;
  short_term_score: number;
  action: string;
  score: StockScoreResponse;
  input_snapshot: Record<string, unknown>;
  created_at: string;
}

export interface ScoreSnapshots {
  ticker: string;
  snapshots: ScoreSnapshot[];
}

export type RefreshTickerResponse = Record<string, unknown>;

export type OperationRecommendationAction = "build_position" | "sell" | "add" | "trim" | "wait_update";

export interface OperationRecommendation {
  action: OperationRecommendationAction;
  label: string;
  reason: string;
}

export interface LatestAnalysisItem {
  ticker: string;
  status: "ready" | "missing";
  date: string | null;
  source: string | null;
  company_name: string | null;
  last_price: number | null;
  medium_term_score: number | null;
  short_term_score: number | null;
  decision_summary: string;
  recommendation: OperationRecommendation;
  factors: FactorScore[];
  risks: string[];
  created_at: string | null;
}

export interface LatestAnalysisResponse {
  tickers: string[];
  updated_after_market_close: boolean;
  items: LatestAnalysisItem[];
}

export interface AdminLoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in_seconds: number;
  expires_at: string;
}

export interface AdminSessionResponse {
  authenticated: boolean;
  role: "admin";
  expires_at: string | null;
}

export interface AdminLogoutResponse {
  status: "logged_out";
}

export interface BacktestRunRequest {
  tickers: string[];
  start_date: string;
  end_date: string;
  initial_cash?: number;
  max_positions?: number;
  position_size_pct?: number | null;
  commission_bps?: number;
  slippage_bps?: number;
}

export interface BacktestMetrics {
  total_return: number;
  annualized_return: number;
  max_drawdown: number;
  win_rate: number;
  trade_count: number;
  average_holding_days: number;
  buy_hold_return: number;
}

export interface BacktestTrade {
  ticker: string;
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  shares: number;
  return_pct: number;
  holding_days: number;
  exit_reason: string;
}

export interface BacktestDailyEquity {
  date: string;
  cash: number;
  positions_value: number;
  total_equity: number;
}

export interface BacktestRunResponse {
  run_id: number;
  strategy_id: number;
  tickers: string[];
  start_date: string;
  end_date: string;
  initial_cash: number;
  metrics: BacktestMetrics;
  trades: BacktestTrade[];
  equity_curve: BacktestDailyEquity[];
}

export interface StoredBacktestRun {
  run_id: number;
  strategy_id: number;
  tickers: string[];
  start_date: string;
  end_date: string;
  initial_cash: number;
  created_at: string;
  total_return: number;
  max_drawdown: number;
  win_rate: number;
  trade_count: number;
  buy_hold_return: number;
}

export interface BacktestRunsResponse {
  runs: StoredBacktestRun[];
}

export interface StrategyVersion {
  strategy_id: number;
  name: string;
  status: "active" | "candidate" | "archived";
  medium_entry_threshold: number;
  short_entry_threshold: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  max_holding_days: number;
  position_size_pct: number;
  created_at: string;
  notes: string;
}

export interface StrategyVersionsResponse {
  strategies: StrategyVersion[];
}

export interface EvolutionRunRequest {
  tickers: string[];
  training_start_date: string;
  training_end_date: string;
  validation_start_date: string;
  validation_end_date: string;
  initial_cash?: number;
}

export interface EvolutionRunResponse {
  candidate_strategy_id: number | null;
  training_run_id: number | null;
  validation_run_id: number | null;
  active_validation_return: number;
  validation_total_return: number;
  max_drawdown: number;
  message: string;
}

export interface HistorySyncRequest {
  tickers: string[];
  end_date?: string;
}

export interface HistorySyncTickerResult {
  ticker: string;
  source: string;
  status: string;
  bars_before: number;
  bars_after: number;
  bars_added: number;
  latest_date: string | null;
  message: string;
}

export interface HistorySyncResponse {
  run_id: number;
  tickers: HistorySyncTickerResult[];
  completed_count: number;
  failed_count: number;
}

export interface StoredHistorySyncRun {
  run_id: number;
  tickers: string[];
  started_at: string;
  completed_at: string | null;
  completed_count: number;
  failed_count: number;
}

export interface HistorySyncRunsResponse {
  runs: StoredHistorySyncRun[];
}

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
  getLatestAnalysis(): Promise<LatestAnalysisResponse>;
  refreshTicker(ticker: string): Promise<RefreshTickerResponse>;
  loginAdmin(username: string, password: string): Promise<AdminLoginResponse>;
  getAdminSession(): Promise<AdminSessionResponse>;
  logoutAdmin(): Promise<AdminLogoutResponse>;
  getBacktestRuns(): Promise<BacktestRunsResponse>;
  runBacktest(request: BacktestRunRequest): Promise<BacktestRunResponse>;
  getStrategyVersions(): Promise<StrategyVersionsResponse>;
  promoteStrategy(strategyId: number): Promise<StrategyVersion>;
  archiveStrategy(strategyId: number): Promise<StrategyVersion>;
  evolveStrategy(request: EvolutionRunRequest): Promise<EvolutionRunResponse>;
  getHistorySyncRuns(): Promise<HistorySyncRunsResponse>;
  syncHistory(request: HistorySyncRequest): Promise<HistorySyncResponse>;
}
