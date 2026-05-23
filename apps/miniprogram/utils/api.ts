import type { StockScorerClient, WxRequestApi } from "@stock-scorer/api-client";

import {
  createStockScorerClient,
  createWxTransport,
  isApiError
} from "@stock-scorer/api-client";

export function createMiniProgramApiClient(baseUrl: string, readToken?: string): StockScorerClient {
  const headers: Record<string, string> = {};
  if (readToken) {
    headers.authorization = `Bearer ${readToken}`;
  }

  return createStockScorerClient({
    baseUrl,
    headers,
    transport: createWxTransport(wx as unknown as WxRequestApi)
  });
}

export function getApiErrorMessage(error: unknown): string {
  if (!isApiError(error)) {
    return "无法连接本地后端服务";
  }

  if (error.code === "not_found") {
    return "没有找到这只股票的数据";
  }

  if (error.code === "service_unavailable" || error.code === "upstream_error") {
    return "数据源暂时不可用，请稍后重试";
  }

  if (error.code === "rate_limited") {
    return "数据源请求过快，请稍后重试";
  }

  if (error.code === "unauthorized" || error.code === "forbidden") {
    return "当前客户端没有访问权限";
  }

  return "请求后端服务失败，请稍后重试";
}
