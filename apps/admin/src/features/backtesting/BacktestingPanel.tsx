import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, LineChart, RefreshCw } from "lucide-react";
import { FormEvent, useState } from "react";

import {
  isApiError,
  type StockScorerClient,
  type StoredBacktestRun,
  type StoredHistorySyncRun,
  type StrategyVersion
} from "@stock-scorer/api-client";

interface BacktestingPanelProps {
  client: StockScorerClient;
}

export function BacktestingPanel({ client }: BacktestingPanelProps) {
  const queryClient = useQueryClient();
  const [tickers, setTickers] = useState("MSFT");
  const [startDate, setStartDate] = useState("2026-01-01");
  const [endDate, setEndDate] = useState("2026-03-31");

  const runsQuery = useQuery({
    queryKey: ["backtest-runs"],
    queryFn: () => client.getBacktestRuns()
  });
  const strategiesQuery = useQuery({
    queryKey: ["strategy-versions"],
    queryFn: () => client.getStrategyVersions()
  });
  const syncRunsQuery = useQuery({
    queryKey: ["history-sync-runs"],
    queryFn: () => client.getHistorySyncRuns()
  });
  const syncMutation = useMutation({
    mutationFn: () =>
      client.syncHistory({
        tickers: parseTickers(tickers),
        end_date: endDate
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["history-sync-runs"] })
  });
  const backtestMutation = useMutation({
    mutationFn: () =>
      client.runBacktest({
        tickers: parseTickers(tickers),
        start_date: startDate,
        end_date: endDate,
        initial_cash: 10_000
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["backtest-runs"] })
  });
  const evolutionMutation = useMutation({
    mutationFn: () =>
      client.evolveStrategy({
        tickers: parseTickers(tickers),
        training_start_date: startDate,
        training_end_date: midpointDate(startDate, endDate),
        validation_start_date: midpointDate(startDate, endDate),
        validation_end_date: endDate,
        initial_cash: 10_000
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["backtest-runs"] });
      queryClient.invalidateQueries({ queryKey: ["strategy-versions"] });
    }
  });

  function submitBacktest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    backtestMutation.mutate();
  }

  return (
    <section className="workspace-band backtesting-panel" aria-labelledby="backtesting-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Research loop</p>
          <h2 id="backtesting-title">回测验证</h2>
        </div>
        <span className="status-pill">
          <LineChart aria-hidden="true" size={16} />
          Strategy lab
        </span>
      </div>

      <form className="research-form" onSubmit={submitBacktest}>
        <label htmlFor="research-tickers">Tickers</label>
        <input id="research-tickers" value={tickers} onChange={(event) => setTickers(event.target.value)} />
        <label htmlFor="research-start">Start</label>
        <input id="research-start" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
        <label htmlFor="research-end">End</label>
        <input id="research-end" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
        <button type="submit" disabled={backtestMutation.isPending}>
          <RefreshCw aria-hidden="true" size={17} className={backtestMutation.isPending ? "spin" : undefined} />
          运行回测
        </button>
        <button type="button" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
          <RefreshCw aria-hidden="true" size={17} className={syncMutation.isPending ? "spin" : undefined} />
          同步历史数据
        </button>
        <button type="button" onClick={() => evolutionMutation.mutate()} disabled={evolutionMutation.isPending}>
          <FlaskConical aria-hidden="true" size={17} />
          生成候选策略
        </button>
      </form>

      {runsQuery.error ? <div className="error-panel">{formatError(runsQuery.error)}</div> : null}
      {strategiesQuery.error ? <div className="error-panel">{formatError(strategiesQuery.error)}</div> : null}
      {syncRunsQuery.error ? <div className="error-panel">{formatError(syncRunsQuery.error)}</div> : null}
      {syncMutation.error ? <div className="error-panel">{formatError(syncMutation.error)}</div> : null}
      {backtestMutation.error ? <div className="error-panel">{formatError(backtestMutation.error)}</div> : null}
      {evolutionMutation.error ? <div className="error-panel">{formatError(evolutionMutation.error)}</div> : null}
      {syncMutation.data?.tickers[0] ? <div className="research-result">{syncMutation.data.tickers[0].message}</div> : null}
      {evolutionMutation.data ? <div className="research-result">{evolutionMutation.data.message}</div> : null}

      <div className="research-grid">
        <div className="panel">
          <h4>最近回测</h4>
          {runsQuery.data?.runs.length ? (
            <div className="research-list">
              {runsQuery.data.runs.slice(0, 4).map((run) => (
                <BacktestRunRow key={run.run_id} run={run} />
              ))}
            </div>
          ) : (
            <div className="empty-state">暂无回测任务。</div>
          )}
        </div>
        <div className="panel">
          <h4>最近同步</h4>
          {syncRunsQuery.data?.runs.length ? (
            <div className="research-list">
              {syncRunsQuery.data.runs.slice(0, 4).map((run) => (
                <SyncRunRow key={run.run_id} run={run} />
              ))}
            </div>
          ) : (
            <div className="empty-state">暂无同步任务。</div>
          )}
        </div>
        <div className="panel">
          <h4>策略版本</h4>
          {strategiesQuery.data?.strategies.length ? (
            <div className="research-list">
              {strategiesQuery.data.strategies.slice(0, 4).map((strategy) => (
                <StrategyRow key={strategy.strategy_id} strategy={strategy} />
              ))}
            </div>
          ) : (
            <div className="empty-state">暂无策略版本。</div>
          )}
        </div>
      </div>
    </section>
  );
}

function SyncRunRow({ run }: { run: StoredHistorySyncRun }) {
  return (
    <div className="research-row">
      <div>
        <strong>Sync #{run.run_id}</strong>
        <span>{run.tickers.join(", ")} · {run.started_at}</span>
      </div>
      <div className="research-metrics">
        <span>{run.completed_count} ok</span>
        <span>{run.failed_count} failed</span>
        <span>{run.completed_at ? "done" : "running"}</span>
      </div>
    </div>
  );
}

function BacktestRunRow({ run }: { run: StoredBacktestRun }) {
  return (
    <div className="research-row">
      <div>
        <strong>Run #{run.run_id}</strong>
        <span>{run.tickers.join(", ")} · {run.start_date} to {run.end_date}</span>
      </div>
      <div className="research-metrics">
        <span>{formatPercent(run.total_return)} return</span>
        <span>{formatPercent(run.max_drawdown)} DD</span>
        <span>{run.trade_count} trades</span>
      </div>
    </div>
  );
}

function StrategyRow({ strategy }: { strategy: StrategyVersion }) {
  return (
    <div className="research-row">
      <div>
        <strong>{strategy.name}</strong>
        <span>{strategy.status} · M{strategy.medium_entry_threshold} / S{strategy.short_entry_threshold}</span>
      </div>
      <div className="research-metrics">
        <span>{formatPercent(strategy.stop_loss_pct)} stop</span>
        <span>{formatPercent(strategy.take_profit_pct)} target</span>
        <span>{strategy.max_holding_days} days</span>
      </div>
    </div>
  );
}

function parseTickers(raw: string): string[] {
  return raw
    .split(",")
    .map((ticker) => ticker.trim().toUpperCase())
    .filter(Boolean);
}

function midpointDate(startDate: string, endDate: string): string {
  const start = new Date(`${startDate}T00:00:00Z`).getTime();
  const end = new Date(`${endDate}T00:00:00Z`).getTime();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
    return startDate;
  }
  return new Date(start + (end - start) / 2).toISOString().slice(0, 10);
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatError(error: unknown): string {
  if (isApiError(error)) {
    return `${error.code}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Research action failed";
}
