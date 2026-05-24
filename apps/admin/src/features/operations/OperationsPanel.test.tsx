import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StockScorerClient } from "@stock-scorer/api-client";

import { OperationsPanel } from "./OperationsPanel";

describe("OperationsPanel", () => {
  it("looks up raw ticker data and triggers refresh through the shared client", async () => {
    const client = {
      getTickerRawData: vi.fn(async (ticker: string) => ({
        ticker,
        source: "fixture",
        raw: { company_name: "Microsoft Corporation" }
      })),
      refreshTicker: vi.fn(async (ticker: string) => ({
        ticker,
        status: "completed"
      }))
    } as unknown as StockScorerClient;

    renderWithQueryClient(<OperationsPanel client={client} />);

    fireEvent.change(screen.getByLabelText("Ops ticker"), { target: { value: "msft" } });
    fireEvent.click(screen.getByRole("button", { name: "查看原始数据" }));

    await waitFor(() => expect(screen.getByText("Microsoft Corporation")).toBeInTheDocument());
    expect(client.getTickerRawData).toHaveBeenCalledWith("MSFT");

    fireEvent.click(screen.getByRole("button", { name: "刷新标的" }));

    await waitFor(() => expect(screen.getByText("completed")).toBeInTheDocument());
    expect(client.refreshTicker).toHaveBeenCalledWith("MSFT");
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
