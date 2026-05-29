import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

    await waitFor(() => expect(screen.getByRole("heading", { name: "盘后分析首页" })).toBeInTheDocument());
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

    await waitFor(() => expect(screen.getByRole("heading", { name: "盘后分析首页" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "工作台登录" })).toBeInTheDocument());
    expect(client.logoutAdmin).toHaveBeenCalled();
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("uses authenticated routes to separate score, strategy, backtest, and operations workspaces", async () => {
    sessionStorage.setItem(STORAGE_KEY, "admin-session-token");
    const client = createTestClient();

    render(<App client={client} />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "盘后分析首页" })).toBeInTheDocument());

    const desktopNav = screen.getByRole("navigation", { name: "Desktop sections" });

    fireEvent.click(within(desktopNav).getByRole("link", { name: "数据查询" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "数据查询" })).toBeInTheDocument());

    fireEvent.click(within(desktopNav).getByRole("link", { name: "策略管理" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "策略管理" })).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "候选审核" })).toBeInTheDocument();

    fireEvent.click(within(desktopNav).getByRole("link", { name: "运维操作" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "运维操作" })).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "数据源状态" })).toBeInTheDocument();
  });

  it("renders a mobile-friendly primary navigation separate from the desktop sider", async () => {
    sessionStorage.setItem(STORAGE_KEY, "admin-session-token");
    window.history.pushState({}, "", "/score");
    const client = createTestClient();

    render(<App client={client} />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "数据查询" })).toBeInTheDocument());

    const mobileNav = screen.getByRole("navigation", { name: "Mobile sections" });
    expect(mobileNav).toBeInTheDocument();
    expect(mobileNav).toHaveClass("mobile-section-tabs");
    expect(within(mobileNav).getByRole("link", { name: "数据查询" })).toBeInTheDocument();
    expect(within(mobileNav).getByRole("link", { name: "运维操作" })).toBeInTheDocument();
  });

  it("renders the homepage with latest post-close analysis and operation recommendations", async () => {
    sessionStorage.setItem(STORAGE_KEY, "admin-session-token");
    window.history.pushState({}, "", "/");
    const client = createTestClient();

    render(<App client={client} />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "盘后分析首页" })).toBeInTheDocument());
    expect(screen.getByText("NVDA")).toBeInTheDocument();
    expect(screen.getByText("NVIDIA Corporation")).toBeInTheDocument();
    expect(screen.getByText("加仓")).toBeInTheDocument();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("等待更新")).toBeInTheDocument();
    expect(client.getLatestAnalysis).toHaveBeenCalled();
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
    getLatestAnalysis: vi.fn(async () => ({
      tickers: ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD", "INTC"],
      updated_after_market_close: true,
      items: [
        {
          ticker: "NVDA",
          status: "ready",
          date: "2026-05-28",
          source: "fmp",
          company_name: "NVIDIA Corporation",
          last_price: 142.5,
          medium_term_score: 88,
          short_term_score: 82,
          decision_summary: "趋势强，允许顺势提高仓位。",
          recommendation: {
            action: "add",
            label: "加仓",
            reason: "中期和短期评分都强。"
          },
          factors: [],
          risks: ["估值偏高"],
          created_at: "2026-05-29T06:30:00"
        },
        {
          ticker: "AAPL",
          status: "missing",
          date: null,
          source: null,
          company_name: null,
          last_price: null,
          medium_term_score: null,
          short_term_score: null,
          decision_summary: "等待盘后数据更新。",
          recommendation: {
            action: "wait_update",
            label: "等待更新",
            reason: "没有可用的盘后分析快照。"
          },
          factors: [],
          risks: [],
          created_at: null
        }
      ]
    })),
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
