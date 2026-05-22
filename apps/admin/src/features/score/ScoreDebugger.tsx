import { useMutation } from "@tanstack/react-query";
import { Activity, AlertTriangle, Play, RefreshCw } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import { isApiError, type StockScorerClient } from "@stock-scorer/api-client";

interface ScoreDebuggerProps {
  client: StockScorerClient;
}

export function ScoreDebugger({ client }: ScoreDebuggerProps) {
  const [ticker, setTicker] = useState("MSFT");
  const [startedAt, setStartedAt] = useState<number | null>(null);

  const scoreMutation = useMutation({
    mutationFn: async (nextTicker: string) => {
      setStartedAt(performance.now());
      return client.getStockScore(nextTicker);
    }
  });

  const elapsedMs = useMemo(() => {
    if (!startedAt || !scoreMutation.submittedAt) {
      return null;
    }
    return Math.round(performance.now() - startedAt);
  }, [startedAt, scoreMutation.submittedAt, scoreMutation.data, scoreMutation.error]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    scoreMutation.mutate(ticker.trim().toUpperCase());
  }

  const score = scoreMutation.data;

  return (
    <section className="workspace-band score-debugger" aria-labelledby="score-debugger-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Score pipeline</p>
          <h2 id="score-debugger-title">评分调试</h2>
        </div>
        <span className="status-pill">
          <Activity aria-hidden="true" size={16} />
          Shared API client
        </span>
      </div>

      <form className="ticker-form" onSubmit={submit}>
        <label htmlFor="ticker">Ticker</label>
        <input
          id="ticker"
          value={ticker}
          onChange={(event) => setTicker(event.target.value)}
          autoCapitalize="characters"
          spellCheck={false}
        />
        <button type="submit" disabled={scoreMutation.isPending}>
          {scoreMutation.isPending ? <RefreshCw aria-hidden="true" className="spin" size={17} /> : <Play aria-hidden="true" size={17} />}
          Run score
        </button>
      </form>

      {scoreMutation.error ? (
        <div className="error-panel" role="alert">
          <AlertTriangle aria-hidden="true" size={18} />
          <span>{formatError(scoreMutation.error)}</span>
        </div>
      ) : null}

      {score ? (
        <div className="score-layout">
          <div className="score-summary">
            <div>
              <span className="mono ticker">{score.ticker}</span>
              <h3>{score.company_name}</h3>
              <p>
                {score.data_source} · {score.data_as_of}
                {elapsedMs !== null ? ` · ${elapsedMs}ms` : ""}
              </p>
            </div>
            <div className="score-metrics">
              <Metric label="Medium" value={score.medium_term_score} tone="gold" />
              <Metric label="Short" value={score.short_term_score} tone="blue" />
              <Metric label="Price" value={`$${score.last_price}`} tone="plain" />
            </div>
          </div>

          <div className="debug-grid">
            <div className="panel">
              <h4>Factor evidence</h4>
              <div className="factor-list">
                {score.factors.map((factor) => (
                  <article key={factor.name} className="factor-row">
                    <div>
                      <strong>{factor.name}</strong>
                      <span>{factor.score}</span>
                    </div>
                    <ul>
                      {factor.evidence.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            </div>

            <div className="panel">
              <h4>Decision</h4>
              <p className="decision-summary">{score.decision.summary}</p>
              <ListBlock title="Triggers" items={score.decision.trigger_conditions} />
              <ListBlock title="Invalidation" items={score.decision.invalidation_conditions} />
              <ListBlock title="Risks" items={score.decision.risks} />
            </div>
          </div>

          <details className="raw-json">
            <summary>Raw response</summary>
            <pre>{JSON.stringify(score, null, 2)}</pre>
          </details>
        </div>
      ) : (
        <div className="empty-state">输入 ticker 后运行评分，后台会显示格式化结果和原始响应。</div>
      )}
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: number | string; tone: "gold" | "blue" | "plain" }) {
  return (
    <div className={`metric metric-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="list-block">
      <span>{title}</span>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function formatError(error: unknown): string {
  if (isApiError(error)) {
    return `${error.code}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Request failed";
}
