import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StockScorerClient } from "@stock-scorer/api-client";

import { BacktestingPanel } from "./BacktestingPanel";

const DEFAULT_BACKTEST_TICKERS = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD", "INTC"];

describe("BacktestingPanel", () => {
  it("renders backtest runs, strategies, and triggers research actions", async () => {
    const client = {
      getBacktestRuns: vi.fn(async () => ({
        runs: [
          {
            run_id: 7,
            strategy_id: 1,
            tickers: ["MSFT"],
            start_date: "2026-01-01",
            end_date: "2026-03-01",
            initial_cash: 10000,
            created_at: "2026-05-26T00:00:00Z",
            total_return: 0.12,
            max_drawdown: 0.03,
            win_rate: 0.6,
            trade_count: 5,
            buy_hold_return: 0.08
          }
        ]
      })),
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
          },
          {
            strategy_id: 2,
            name: "candidate-v2",
            status: "candidate",
            medium_entry_threshold: 60,
            short_entry_threshold: 55,
            stop_loss_pct: 0.07,
            take_profit_pct: 0.22,
            max_holding_days: 18,
            position_size_pct: 0.5,
            created_at: "2026-05-26T00:10:00Z",
            notes: "Candidate strategy"
          }
        ]
      })),
      getHistorySyncRuns: vi.fn(async () => ({
        runs: [
          {
            run_id: 3,
            tickers: ["MSFT"],
            started_at: "2026-05-26T00:00:00Z",
            completed_at: "2026-05-26T00:01:00Z",
            completed_count: 1,
            failed_count: 0
          }
        ]
      })),
      syncHistory: vi.fn(async () => ({
        run_id: 4,
        tickers: [
          {
            ticker: "MSFT",
            source: "fmp",
            status: "completed",
            bars_before: 1,
            bars_after: 3,
            bars_added: 2,
            latest_date: "2026-03-01",
            message: "Synced 3 bars from fmp."
          }
        ],
        completed_count: 1,
        failed_count: 0
      })),
      runBacktest: vi.fn(async () => ({
        run_id: 8,
        strategy_id: 1,
        tickers: ["MSFT"],
        start_date: "2026-01-01",
        end_date: "2026-03-01",
        initial_cash: 10000,
        metrics: {
          total_return: 0.1,
          annualized_return: 0.4,
          max_drawdown: 0.02,
          win_rate: 0.5,
          trade_count: 4,
          average_holding_days: 8,
          buy_hold_return: 0.07
        },
        trades: []
      })),
      evolveStrategy: vi.fn(async () => ({
        candidate_strategy_id: 2,
        training_run_id: 9,
        validation_run_id: 10,
        active_validation_return: 0.04,
        validation_total_return: 0.06,
        max_drawdown: 0.02,
        message: "Candidate strategy generated."
      })),
      promoteStrategy: vi.fn(async () => ({
        strategy_id: 2,
        name: "candidate-v2",
        status: "active",
        medium_entry_threshold: 60,
        short_entry_threshold: 55,
        stop_loss_pct: 0.07,
        take_profit_pct: 0.22,
        max_holding_days: 18,
        position_size_pct: 0.5,
        created_at: "2026-05-26T00:10:00Z",
        notes: "Candidate strategy"
      })),
      archiveStrategy: vi.fn(async () => ({
        strategy_id: 2,
        name: "candidate-v2",
        status: "archived",
        medium_entry_threshold: 60,
        short_entry_threshold: 55,
        stop_loss_pct: 0.07,
        take_profit_pct: 0.22,
        max_holding_days: 18,
        position_size_pct: 0.5,
        created_at: "2026-05-26T00:10:00Z",
        notes: "Candidate strategy"
      }))
    } as unknown as StockScorerClient;

    renderWithQueryClient(<BacktestingPanel client={client} />);

    await waitFor(() => expect(screen.getByText("Run #7")).toBeInTheDocument());
    expect(screen.getByLabelText("Tickers")).toHaveValue(DEFAULT_BACKTEST_TICKERS.join(","));
    expect(screen.getAllByText("default-v1").length).toBeGreaterThan(0);
    expect(screen.getByText("Sync #3")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "同步历史数据" }));
    await waitFor(() => expect(screen.getByText("Synced 3 bars from fmp.")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "运行回测" }));
    await waitFor(() => expect(client.runBacktest).toHaveBeenCalled());
    expect(client.runBacktest).toHaveBeenCalledWith(expect.objectContaining({ tickers: DEFAULT_BACKTEST_TICKERS }));

    fireEvent.click(screen.getByRole("button", { name: "生成候选策略" }));
    await waitFor(() => expect(screen.getByText("Candidate strategy generated.")).toBeInTheDocument());
    expect(client.evolveStrategy).toHaveBeenCalledWith(expect.objectContaining({ tickers: DEFAULT_BACKTEST_TICKERS }));

    fireEvent.click(screen.getByRole("button", { name: "晋升 candidate-v2" }));
    await waitFor(() => expect(client.promoteStrategy).toHaveBeenCalledWith(2));

    fireEvent.click(screen.getByRole("button", { name: "归档 candidate-v2" }));
    await waitFor(() => expect(client.archiveStrategy).toHaveBeenCalledWith(2));
  });
});

function renderWithQueryClient(children: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>);
}
