import { useQuery } from "@tanstack/react-query";
import { Database, KeyRound, RefreshCw } from "lucide-react";

import type { StockScorerClient } from "@stock-scorer/api-client";

interface ProviderStatusProps {
  client: StockScorerClient;
}

interface ProviderStatusResponse {
  active_source?: string;
  providers?: Record<string, { name?: string; api_key_configured?: boolean; active?: boolean }>;
}

export function ProviderStatus({ client }: ProviderStatusProps) {
  const query = useQuery({
    queryKey: ["provider-status"],
    queryFn: () => client.getProviderStatus() as Promise<ProviderStatusResponse>,
    retry: false
  });

  const providers = Object.entries(query.data?.providers || {});

  return (
    <section className="workspace-band" aria-labelledby="provider-status-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Operations</p>
          <h2 id="provider-status-title">数据源状态</h2>
        </div>
        <button className="icon-button" type="button" onClick={() => void query.refetch()} aria-label="Refresh provider status">
          <RefreshCw aria-hidden="true" size={17} />
        </button>
      </div>

      {query.isError ? <div className="error-panel">Provider status endpoint unavailable</div> : null}
      {query.isPending ? <div className="empty-state">Loading provider status...</div> : null}

      {query.data ? (
        <div className="provider-table" role="table" aria-label="Provider status">
          <div className="provider-row provider-head" role="row">
            <span role="columnheader">Provider</span>
            <span role="columnheader">Key</span>
            <span role="columnheader">Mode</span>
          </div>
          {providers.map(([key, provider]) => (
            <div className="provider-row" role="row" key={key}>
              <span role="cell">
                <Database aria-hidden="true" size={15} />
                {provider.name || key}
              </span>
              <span role="cell" className={provider.api_key_configured ? "ok" : "warn"}>
                <KeyRound aria-hidden="true" size={15} />
                {provider.api_key_configured ? "configured" : "missing"}
              </span>
              <span role="cell">{provider.active ? "active" : "standby"}</span>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
