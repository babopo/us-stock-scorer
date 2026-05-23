import assert from "node:assert/strict";
import { test } from "node:test";

const DEPLOYED_API_BASE_URL = "http://47.90.148.197/";

test("mini program uses the deployed API server by default", async () => {
  const previousApp = (globalThis as typeof globalThis & { App?: unknown }).App;
  let appOptions: unknown;

  (globalThis as typeof globalThis & { App: (options: unknown) => unknown }).App = (options) => {
    appOptions = options;
    return options;
  };

  try {
    await import("../../app.js");
  } finally {
    (globalThis as typeof globalThis & { App?: unknown }).App = previousApp;
  }

  assert.equal(
    (appOptions as { globalData?: { apiBaseUrl?: string } }).globalData?.apiBaseUrl,
    DEPLOYED_API_BASE_URL
  );
});
