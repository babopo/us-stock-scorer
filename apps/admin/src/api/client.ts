import {
  createFetchTransport,
  createStockScorerClient,
  type FetchLike,
  type StockScorerClient
} from "@stock-scorer/api-client";

export interface AdminApiClientOptions {
  baseUrl?: string;
  adminToken?: string;
  fetchImpl?: FetchLike;
}

export function createAdminApiClient(options: AdminApiClientOptions = {}): StockScorerClient {
  const headers: Record<string, string> = {};
  if (options.adminToken) {
    headers.authorization = `Bearer ${options.adminToken}`;
  }

  return createStockScorerClient({
    baseUrl: options.baseUrl || "",
    headers,
    transport: createFetchTransport(options.fetchImpl)
  });
}

export function createDefaultAdminApiClient(): StockScorerClient {
  return createAdminApiClient({
    baseUrl: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
    adminToken: import.meta.env.VITE_ADMIN_AUTH_TOKEN || undefined
  });
}
