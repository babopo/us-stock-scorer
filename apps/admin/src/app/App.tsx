import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useMemo } from "react";

import type { StockScorerClient } from "@stock-scorer/api-client";

import { createDefaultAdminApiClient } from "../api/client";
import { OperationsPanel } from "../features/operations/OperationsPanel";
import { ProviderStatus } from "../features/providers/ProviderStatus";
import { ScoreDebugger } from "../features/score/ScoreDebugger";

interface AppProps {
  client?: StockScorerClient;
}

export function App({ client }: AppProps) {
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: false,
            refetchOnWindowFocus: false
          },
          mutations: {
            retry: false
          }
        }
      }),
    []
  );
  const apiClient = useMemo(() => client || createDefaultAdminApiClient(), [client]);

  return (
    <QueryClientProvider client={queryClient}>
      <main className="admin-shell">
        <header className="topbar">
          <div>
            <p className="eyebrow">US Stock Scorer</p>
            <h1>后台管理</h1>
          </div>
          <nav aria-label="Admin sections">
            <a href="#score-debugger-title">Score</a>
            <a href="#provider-status-title">Providers</a>
            <a href="#operations-title">Ops</a>
          </nav>
        </header>
        <div className="workspace">
          <ScoreDebugger client={apiClient} />
          <div className="side-stack">
            <ProviderStatus client={apiClient} />
            <OperationsPanel client={apiClient} />
          </div>
        </div>
      </main>
    </QueryClientProvider>
  );
}
