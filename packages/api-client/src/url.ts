import type { QueryParams } from "./types";

export function joinUrl(baseUrl: string, path: string): string {
  const cleanBaseUrl = String(baseUrl || "").replace(/\/+$/, "");
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${cleanBaseUrl}${cleanPath}`;
}

export function appendQuery(url: string, query?: QueryParams): string {
  const entries = Object.entries(query || {}).filter(([, value]) => value !== undefined && value !== null);
  if (!entries.length) {
    return url;
  }

  const queryString = entries
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join("&");

  return `${url}${url.includes("?") ? "&" : "?"}${queryString}`;
}
