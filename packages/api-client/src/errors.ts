import type { ApiErrorCode, ApiErrorOptions, ApiResponse, HeaderMap } from "./types";

const ERROR_CODE_BY_STATUS: Partial<Record<number, ApiErrorCode>> = {
  400: "bad_request",
  401: "unauthorized",
  403: "forbidden",
  404: "not_found",
  429: "rate_limited",
  502: "upstream_error",
  503: "service_unavailable"
};

export class ApiError extends Error {
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

export function getErrorCode(status: number): ApiErrorCode {
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

export function createApiError(response: ApiResponse<unknown> & { headers: HeaderMap }): ApiError {
  const status = response.status;
  const detail = getErrorDetail(response.data);
  const requestId = getHeader(response.headers, "x-request-id");
  return new ApiError({
    status,
    detail,
    code: getErrorCode(status),
    ...(requestId ? { requestId } : {})
  });
}

export function isApiError(error: unknown): error is ApiError {
  return (
    error instanceof ApiError ||
    Boolean(
      error &&
        typeof error === "object" &&
        "name" in error &&
        (error as { name?: unknown }).name === "ApiError"
    )
  );
}
