const ERROR_CODE_BY_STATUS = {
  400: "bad_request",
  401: "unauthorized",
  403: "forbidden",
  404: "not_found",
  429: "rate_limited",
  502: "upstream_error",
  503: "service_unavailable"
};

class ApiError extends Error {
  constructor({ status, code, detail, requestId, message }) {
    super(message || getErrorMessage(detail, code));
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.requestId = requestId;
  }
}

function getErrorCode(status) {
  return ERROR_CODE_BY_STATUS[status] || (status >= 500 ? "internal_error" : "request_failed");
}

function getErrorDetail(data) {
  if (data && typeof data === "object" && Object.prototype.hasOwnProperty.call(data, "detail")) {
    return data.detail;
  }
  return data;
}

function getErrorMessage(detail, code) {
  if (typeof detail === "string" && detail) {
    return detail;
  }
  return code || "request_failed";
}

function getHeader(headers, name) {
  if (!headers) {
    return undefined;
  }
  const lowerName = name.toLowerCase();
  const found = Object.keys(headers).find((key) => key.toLowerCase() === lowerName);
  return found ? headers[found] : undefined;
}

function createApiError(response) {
  const status = response.status;
  const detail = getErrorDetail(response.data);
  return new ApiError({
    status,
    detail,
    code: getErrorCode(status),
    requestId: getHeader(response.headers, "x-request-id")
  });
}

function isApiError(error) {
  return error instanceof ApiError || Boolean(error && error.name === "ApiError");
}

module.exports = {
  ApiError,
  createApiError,
  getErrorCode,
  isApiError
};
