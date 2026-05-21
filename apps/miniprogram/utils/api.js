const {
  createStockScorerClient,
  createWxTransport,
  isApiError
} = require("@stock-scorer/api-client");

function createMiniProgramApiClient(baseUrl) {
  return createStockScorerClient({
    baseUrl,
    transport: createWxTransport(wx)
  });
}

function getApiErrorMessage(error) {
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

  return "请求后端服务失败，请稍后重试";
}

module.exports = {
  createMiniProgramApiClient,
  getApiErrorMessage
};
