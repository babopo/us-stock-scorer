import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { StockScorerClient, StockScoreResponse } from "@stock-scorer/api-client";

import { ScoreDebugger } from "./ScoreDebugger";

const sampleScore: StockScoreResponse = {
  ticker: "MSFT",
  company_name: "Microsoft Corporation",
  last_price: 420.5,
  medium_term_score: 82,
  medium_term_label: "positive",
  short_term_score: 74,
  short_term_label: "probe",
  factors: [
    {
      name: "质量/盈利",
      score: 90,
      evidence: ["ROIC 强", "利润率稳定"]
    },
    {
      name: "估值",
      score: 62,
      evidence: ["估值高于市场中位数"]
    },
    {
      name: "成长与预期",
      score: 84,
      evidence: ["云业务增长稳定"]
    },
    {
      name: "投资纪律/财务稳健",
      score: 86,
      evidence: ["资产负债表稳健"]
    },
    {
      name: "中期动量与风险",
      score: 78,
      evidence: ["相对 QQQ 保持强势"]
    }
  ],
  decision: {
    action: "small_probe",
    summary: "小仓试探",
    trigger_conditions: ["突破前高"],
    invalidation_conditions: ["跌破支撑"],
    risks: ["估值偏高"]
  },
  data_as_of: "2026-05-22",
  data_source: "fixture"
};

describe("ScoreDebugger", () => {
  it("queries the shared client and renders score evidence", async () => {
    const client = {
      getStockScore: async (ticker: string) => ({ ...sampleScore, ticker })
    } as StockScorerClient;

    renderWithQueryClient(<ScoreDebugger client={client} />);

    fireEvent.change(screen.getByLabelText("Ticker"), { target: { value: "msft" } });
    fireEvent.click(screen.getByRole("button", { name: "生成评分" }));

    await waitFor(() => expect(screen.getByText("MSFT")).toBeInTheDocument());
    expect(screen.getByText("Microsoft Corporation")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "六维图" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /MSFT 六维评分雷达图/ })).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.getByText("ROIC 强")).toBeInTheDocument();
    expect(screen.getByText("突破前高")).toBeInTheDocument();
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
