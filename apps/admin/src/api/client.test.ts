import { describe, expect, it, vi } from "vitest";

import { createAdminApiClient, resolveDefaultApiBaseUrl } from "./client";

describe("createAdminApiClient", () => {
  it("uses the shared API client with fetch transport and admin auth header", async () => {
    const fetchImpl = vi.fn(async (url: string, init: RequestInit) => ({
      status: 200,
      headers: new Headers(),
      text: async () => JSON.stringify({ status: "ok" })
    })) as unknown as typeof fetch;

    const client = createAdminApiClient({
      baseUrl: "http://127.0.0.1:8000/",
      adminToken: "local-token",
      fetchImpl
    });

    await client.getHealth();

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/health",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          authorization: "Bearer local-token"
        })
      })
    );
  });

  it("defaults to same-origin API requests for production deployment", () => {
    expect(resolveDefaultApiBaseUrl(undefined)).toBe("");
  });

  it("uses an explicit API base URL when configured", () => {
    expect(resolveDefaultApiBaseUrl("https://stocks.example.com")).toBe("https://stocks.example.com");
  });
});
