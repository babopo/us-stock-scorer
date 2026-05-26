import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { ApiError, type StockScorerClient } from "@stock-scorer/api-client";

import { App } from "./App";

const STORAGE_KEY = "stock-scorer-admin-token";

describe("App auth gate", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("shows the login form when there is no stored admin session", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "工作台登录" })).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("logs in and renders the admin dashboard", async () => {
    const client = createTestClient();

    render(<App client={client} />);

    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "六维评分雷达" })).toBeInTheDocument());
    expect(client.loginAdmin).toHaveBeenCalledWith("admin", "secret-password");
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe("admin-session-token");
  });

  it("clears a stored token when the session check returns unauthorized", async () => {
    sessionStorage.setItem(STORAGE_KEY, "stale-token");
    const client = createTestClient({
      getAdminSession: vi.fn(async () => {
        throw new ApiError({
          status: 401,
          code: "unauthorized",
          detail: "Invalid bearer token"
        });
      })
    });

    render(<App client={client} />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "工作台登录" })).toBeInTheDocument());
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("logs out and returns to the login form", async () => {
    sessionStorage.setItem(STORAGE_KEY, "admin-session-token");
    const client = createTestClient();

    render(<App client={client} />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "六维评分雷达" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "工作台登录" })).toBeInTheDocument());
    expect(client.logoutAdmin).toHaveBeenCalled();
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("uses authenticated routes to separate score, strategy, backtest, and operations workspaces", async () => {
    sessionStorage.setItem(STORAGE_KEY, "admin-session-token");
    const client = createTestClient();

    render(<App client={client} />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "数据查询" })).toBeInTheDocument());

    fireEvent.click(screen.getByRole("link", { name: "策略管理" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "策略管理" })).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "候选审核" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "运维操作" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "运维操作" })).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "数据源状态" })).toBeInTheDocument();
  });
});

function createTestClient(overrides: Partial<StockScorerClient> = {}): StockScorerClient {
  return {
    getHealth: vi.fn(async () => ({ status: "ok" })),
    getStockScore: vi.fn(),
    getProviderStatus: vi.fn(async () => ({
      active_source: "fixture",
      providers: {
        fixture: { name: "fixture", api_key_configured: true, active: true }
      }
    })),
    getTickerRawData: vi.fn(),
    getScoreSnapshots: vi.fn(),
    refreshTicker: vi.fn(),
    getBacktestRuns: vi.fn(async () => ({ runs: [] })),
    runBacktest: vi.fn(),
    getStrategyVersions: vi.fn(async () => ({
      strategies: [
        {
          strategy_id: 1,
          name: "default-v1",
          status: "active",
          medium_entry_threshold: 65,
          short_entry_threshold: 60,
          stop_loss_pct: 0.08,
          take_profit_pct: 0.18,
          max_holding_days: 20,
          position_size_pct: 1,
          created_at: "2026-05-26T00:00:00Z",
          notes: "Initial strategy"
        }
      ]
    })),
    promoteStrategy: vi.fn(),
    archiveStrategy: vi.fn(),
    evolveStrategy: vi.fn(),
    getHistorySyncRuns: vi.fn(async () => ({ runs: [] })),
    syncHistory: vi.fn(),
    loginAdmin: vi.fn(async () => ({
      access_token: "admin-session-token",
      token_type: "bearer",
      expires_in_seconds: 43200,
      expires_at: "2026-05-23T12:00:00Z"
    })),
    getAdminSession: vi.fn(async () => ({
      authenticated: true,
      role: "admin",
      expires_at: "2026-05-23T12:00:00Z"
    })),
    logoutAdmin: vi.fn(async () => ({ status: "logged_out" })),
    ...overrides
  } as StockScorerClient;
}
