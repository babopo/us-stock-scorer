import { useMutation } from "@tanstack/react-query";
import { DatabaseZap, RefreshCw, Search } from "lucide-react";
import { FormEvent, useState } from "react";

import { isApiError, type StockScorerClient } from "@stock-scorer/api-client";

interface OperationsPanelProps {
  client: StockScorerClient;
}

export function OperationsPanel({ client }: OperationsPanelProps) {
  const [ticker, setTicker] = useState("MSFT");

  const rawDataMutation = useMutation({
    mutationFn: (nextTicker: string) => client.getTickerRawData(nextTicker)
  });
  const refreshMutation = useMutation({
    mutationFn: (nextTicker: string) => client.refreshTicker(nextTicker)
  });

  function normalizedTicker() {
    return ticker.trim().toUpperCase();
  }

  function inspectRawData(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    rawDataMutation.mutate(normalizedTicker());
  }

  function refreshTicker() {
    refreshMutation.mutate(normalizedTicker());
  }

  return (
    <section className="workspace-band operations-panel" aria-labelledby="operations-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Admin API</p>
          <h2 id="operations-title">运维操作</h2>
        </div>
        <span className="status-pill">
          <DatabaseZap aria-hidden="true" size={16} />
          Raw + refresh
        </span>
      </div>

      <form className="ticker-form" onSubmit={inspectRawData}>
        <label htmlFor="ops-ticker">Ops ticker</label>
        <input
          id="ops-ticker"
          value={ticker}
          onChange={(event) => setTicker(event.target.value)}
          autoCapitalize="characters"
          spellCheck={false}
        />
        <button type="submit" disabled={rawDataMutation.isPending}>
          <Search aria-hidden="true" size={17} />
          Inspect raw data
        </button>
        <button type="button" onClick={refreshTicker} disabled={refreshMutation.isPending}>
          <RefreshCw aria-hidden="true" size={17} className={refreshMutation.isPending ? "spin" : undefined} />
          Refresh ticker
        </button>
      </form>

      {rawDataMutation.error ? <div className="error-panel">{formatError(rawDataMutation.error)}</div> : null}
      {refreshMutation.error ? <div className="error-panel">{formatError(refreshMutation.error)}</div> : null}

      <div className="operations-grid">
        <div className="panel">
          <h4>Raw data</h4>
          {rawDataMutation.data ? (
            <>
              <div className="ops-summary">
                <strong>{readTicker(rawDataMutation.data)}</strong>
                <span>{readCompanyName(rawDataMutation.data)}</span>
              </div>
              <pre className="compact-json">{JSON.stringify(rawDataMutation.data, null, 2)}</pre>
            </>
          ) : (
            <div className="empty-state">查询 fixture 原始数据，用于排查评分输入。</div>
          )}
        </div>
        <div className="panel">
          <h4>Refresh result</h4>
          {refreshMutation.data ? (
            <>
              <div className="ops-summary">
                <strong>{readTicker(refreshMutation.data)}</strong>
                <span>{readStatus(refreshMutation.data)}</span>
              </div>
              <pre className="compact-json">{JSON.stringify(refreshMutation.data, null, 2)}</pre>
            </>
          ) : (
            <div className="empty-state">触发单只股票刷新，当前 fixture 模式会复用评分流水线。</div>
          )}
        </div>
      </div>
    </section>
  );
}

function formatError(error: unknown): string {
  if (isApiError(error)) {
    return `${error.code}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Operation failed";
}

function readTicker(value: unknown): string {
  return readStringField(value, "ticker") || "UNKNOWN";
}

function readStatus(value: unknown): string {
  return readStringField(value, "status") || "done";
}

function readCompanyName(value: unknown): string {
  if (!value || typeof value !== "object") {
    return "raw response";
  }
  const raw = (value as { raw?: unknown }).raw;
  return readStringField(raw, "company_name") || "raw response";
}

function readStringField(value: unknown, key: string): string | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const field = (value as Record<string, unknown>)[key];
  return typeof field === "string" ? field : null;
}
