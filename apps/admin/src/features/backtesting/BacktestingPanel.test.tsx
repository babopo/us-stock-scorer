import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StockScorerClient } from "@stock-scorer/api-client";

import { BacktestingPanel } from "./BacktestingPanel";

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
          }
        ]
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
      }))
    } as unknown as StockScorerClient;

    renderWithQueryClient(<BacktestingPanel client={client} />);

    await waitFor(() => expect(screen.getByText("Run #7")).toBeInTheDocument());
    expect(screen.getByText("default-v1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "运行回测" }));
    await waitFor(() => expect(client.runBacktest).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "生成候选策略" }));
    await waitFor(() => expect(screen.getByText("Candidate strategy generated.")).toBeInTheDocument());
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

