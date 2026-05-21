import type { ApiRequest, ApiResponse, ApiTransport, HeaderMap } from "../types";
import { appendQuery } from "../url";

interface FetchRequestInit {
  method: string;
  headers: HeaderMap;
  body?: string;
  signal?: AbortSignal;
}

interface FetchHeaders {
  forEach(callback: (value: string, key: string) => void): void;
}

interface FetchResponse {
  status: number;
  headers?: FetchHeaders;
  text(): Promise<string>;
}

export type FetchLike = (url: string, init: FetchRequestInit) => Promise<FetchResponse>;

export function createFetchTransport(fetchImpl?: FetchLike): ApiTransport {
  const requestFetch = (fetchImpl || globalThis.fetch) as FetchLike | undefined;

  if (typeof requestFetch !== "function") {
    throw new TypeError("createFetchTransport requires a fetch implementation");
  }

  return async function fetchTransport<T>(request: ApiRequest): Promise<ApiResponse<T>> {
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timeoutId =
      controller && request.timeoutMs
        ? setTimeout(() => {
            controller.abort();
          }, request.timeoutMs)
        : null;

    try {
      const init: FetchRequestInit = {
        method: request.method,
        headers: buildHeaders(request.headers, request.body)
      };

      if (request.body !== undefined) {
        init.body = JSON.stringify(request.body);
      }
      if (controller) {
        init.signal = controller.signal;
      }

      const response = await requestFetch(appendQuery(request.url, request.query), init);

      return {
        status: response.status,
        headers: headersToObject(response.headers),
        data: (await parseResponseBody(response)) as T
      };
    } finally {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    }
  };
}

function buildHeaders(headers: HeaderMap | undefined, body: unknown): HeaderMap {
  const nextHeaders = Object.assign({}, headers || {});
  const hasContentType = Object.keys(nextHeaders).some((key) => key.toLowerCase() === "content-type");

  if (body !== undefined && !hasContentType) {
    nextHeaders["content-type"] = "application/json";
  }

  return nextHeaders;
}

async function parseResponseBody(response: FetchResponse): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function headersToObject(headers: FetchHeaders | undefined): HeaderMap {
  const result: HeaderMap = {};
  if (!headers || typeof headers.forEach !== "function") {
    return result;
  }

  headers.forEach((value, key) => {
    result[key] = value;
  });
  return result;
}
