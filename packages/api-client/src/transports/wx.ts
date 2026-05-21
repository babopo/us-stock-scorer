import type { ApiRequest, ApiResponse, ApiTransport, HeaderMap, HttpMethod } from "../types";
import { appendQuery } from "../url";

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

export interface WxRequestApi {
  request<T = unknown>(options: WxRequestOptions<T>): void;
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
