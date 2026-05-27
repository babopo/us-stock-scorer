import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, CheckCircle2, FlaskConical, LineChart, RefreshCw, ShieldCheck } from "lucide-react";
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
  view?: "all" | "strategy" | "backtests";
}

const DEFAULT_RESEARCH_TICKERS = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD", "INTC"].join(",");

export function BacktestingPanel({ client, view = "all" }: BacktestingPanelProps) {
  const queryClient = useQueryClient();
  const [tickers, setTickers] = useState(DEFAULT_RESEARCH_TICKERS);
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
  const promoteMutation = useMutation({
    mutationFn: (strategyId: number) => client.promoteStrategy(strategyId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["strategy-versions"] })
  });
  const archiveMutation = useMutation({
    mutationFn: (strategyId: number) => client.archiveStrategy(strategyId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["strategy-versions"] })
  });
  const strategies = strategiesQuery.data?.strategies ?? [];
  const activeStrategy = strategies.find((strategy) => strategy.status === "active");
  const candidateCount = strategies.filter((strategy) => strategy.status === "candidate").length;
  const showStrategy = view === "all" || view === "strategy";
  const showBacktests = view === "all" || view === "backtests";
  const showSync = view === "all";

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

      {showStrategy ? <div className="strategy-command-strip" aria-label="Strategy review summary">
        <div>
          <span>Active strategy</span>
          <strong>{activeStrategy ? activeStrategy.name : "未加载"}</strong>
        </div>
        <div>
          <span>Review queue</span>
          <strong>{candidateCount} candidate</strong>
        </div>
        <div>
          <span>Latest window</span>
          <strong>{startDate} / {endDate}</strong>
        </div>
      </div> : null}

      <form className="research-form" onSubmit={submitBacktest}>
        <div className="field-control">
          <label htmlFor="research-tickers">Tickers</label>
          <input id="research-tickers" value={tickers} onChange={(event) => setTickers(event.target.value)} />
        </div>
        <div className="field-control">
          <label htmlFor="research-start">Start</label>
          <input id="research-start" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
        </div>
        <div className="field-control">
          <label htmlFor="research-end">End</label>
          <input id="research-end" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
        </div>
        <div className="research-actions">
          {showBacktests ? <button type="submit" disabled={backtestMutation.isPending}>
            <RefreshCw aria-hidden="true" size={17} className={backtestMutation.isPending ? "spin" : undefined} />
            运行回测
          </button> : null}
          {showSync ? <button type="button" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
            <RefreshCw aria-hidden="true" size={17} className={syncMutation.isPending ? "spin" : undefined} />
            同步历史数据
          </button> : null}
          {showStrategy ? <button type="button" onClick={() => evolutionMutation.mutate()} disabled={evolutionMutation.isPending}>
            <FlaskConical aria-hidden="true" size={17} />
            生成候选策略
          </button> : null}
        </div>
      </form>

      {runsQuery.error ? <div className="error-panel">{formatError(runsQuery.error)}</div> : null}
      {strategiesQuery.error ? <div className="error-panel">{formatError(strategiesQuery.error)}</div> : null}
      {syncRunsQuery.error ? <div className="error-panel">{formatError(syncRunsQuery.error)}</div> : null}
      {syncMutation.error ? <div className="error-panel">{formatError(syncMutation.error)}</div> : null}
      {backtestMutation.error ? <div className="error-panel">{formatError(backtestMutation.error)}</div> : null}
      {evolutionMutation.error ? <div className="error-panel">{formatError(evolutionMutation.error)}</div> : null}
      {promoteMutation.error ? <div className="error-panel">{formatError(promoteMutation.error)}</div> : null}
      {archiveMutation.error ? <div className="error-panel">{formatError(archiveMutation.error)}</div> : null}
      {syncMutation.data?.tickers[0] ? <div className="research-result">{syncMutation.data.tickers[0].message}</div> : null}
      {evolutionMutation.data ? <div className="research-result">{evolutionMutation.data.message}</div> : null}

      <div className="research-grid">
        {showStrategy ? <div className="panel strategy-review-panel">
          <div className="panel-heading">
            <h4>候选审核</h4>
            <span>{candidateCount} pending</span>
          </div>
          {strategies.length ? (
            <div className="research-list">
              {strategies.slice(0, 6).map((strategy) => (
                <StrategyRow
                  key={strategy.strategy_id}
                  strategy={strategy}
                  activeStrategy={activeStrategy}
                  onPromote={(strategyId) => promoteMutation.mutate(strategyId)}
                  onArchive={(strategyId) => archiveMutation.mutate(strategyId)}
                  actionPending={promoteMutation.isPending || archiveMutation.isPending}
                />
              ))}
            </div>
          ) : (
            <div className="empty-state">暂无策略版本。</div>
          )}
        </div> : null}
        {showBacktests ? <div className="panel">
          <div className="panel-heading">
            <h4>最近回测</h4>
            <span>{runsQuery.data?.runs.length ?? 0} runs</span>
          </div>
          {runsQuery.data?.runs.length ? (
            <div className="research-list">
              {runsQuery.data.runs.slice(0, 4).map((run) => (
                <BacktestRunRow key={run.run_id} run={run} />
              ))}
            </div>
          ) : (
            <div className="empty-state">暂无回测任务。</div>
          )}
        </div> : null}
        {showSync ? <div className="panel">
          <div className="panel-heading">
            <h4>最近同步</h4>
            <span>{syncRunsQuery.data?.runs.length ?? 0} jobs</span>
          </div>
          {syncRunsQuery.data?.runs.length ? (
            <div className="research-list">
              {syncRunsQuery.data.runs.slice(0, 4).map((run) => (
                <SyncRunRow key={run.run_id} run={run} />
              ))}
            </div>
          ) : (
            <div className="empty-state">暂无同步任务。</div>
          )}
        </div> : null}
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

function StrategyRow({
  strategy,
  activeStrategy,
  onPromote,
  onArchive,
  actionPending
}: {
  strategy: StrategyVersion;
  activeStrategy: StrategyVersion | undefined;
  onPromote(strategyId: number): void;
  onArchive(strategyId: number): void;
  actionPending: boolean;
}) {
  const isCandidate = strategy.status === "candidate";
  const comparison = activeStrategy && strategy.strategy_id !== activeStrategy.strategy_id ? buildStrategyComparison(strategy, activeStrategy) : [];
  return (
    <div className={`research-row strategy-row strategy-row-${strategy.status}`}>
      <div>
        <div className="strategy-title-line">
          <strong>{strategy.name}</strong>
          <span className={`strategy-status strategy-status-${strategy.status}`}>{strategy.status}</span>
        </div>
        <span>M{strategy.medium_entry_threshold} / S{strategy.short_entry_threshold} · Size {formatPercent(strategy.position_size_pct)}</span>
      </div>
      <div className="research-metrics">
        <span>{formatPercent(strategy.stop_loss_pct)} stop</span>
        <span>{formatPercent(strategy.take_profit_pct)} target</span>
        <span>{strategy.max_holding_days} days</span>
      </div>
      {comparison.length ? (
        <div className="strategy-comparison" aria-label={`${strategy.name} 相对当前启用策略的指标差异`}>
          <div className="strategy-comparison-heading">
            <span>相对当前</span>
            <strong>{activeStrategy?.name}</strong>
          </div>
          <div className="strategy-delta-grid">
            {comparison.map((item) => (
              <div key={item.label} className={`strategy-delta strategy-delta-${item.tone}`}>
                <span>{item.label}</span>
                <strong>{item.delta}</strong>
                <em>{item.message}</em>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {isCandidate ? (
        <div className="strategy-actions">
          <button type="button" className="review-button review-button-primary" onClick={() => onPromote(strategy.strategy_id)} disabled={actionPending} aria-label={`晋升 ${strategy.name}`}>
            <CheckCircle2 aria-hidden="true" size={15} />
            晋升
          </button>
          <button type="button" className="review-button" onClick={() => onArchive(strategy.strategy_id)} disabled={actionPending} aria-label={`归档 ${strategy.name}`}>
            <Archive aria-hidden="true" size={15} />
            归档
          </button>
        </div>
      ) : strategy.status === "active" ? (
        <div className="strategy-active-note">
          <ShieldCheck aria-hidden="true" size={15} />
          当前启用
        </div>
      ) : null}
    </div>
  );
}

function buildStrategyComparison(strategy: StrategyVersion, activeStrategy: StrategyVersion) {
  const mediumDelta = strategy.medium_entry_threshold - activeStrategy.medium_entry_threshold;
  const shortDelta = strategy.short_entry_threshold - activeStrategy.short_entry_threshold;
  const entryDelta = mediumDelta + shortDelta;
  const stopLossDelta = strategy.stop_loss_pct - activeStrategy.stop_loss_pct;
  const targetDelta = strategy.take_profit_pct - activeStrategy.take_profit_pct;
  const holdingDaysDelta = strategy.max_holding_days - activeStrategy.max_holding_days;
  const positionDelta = strategy.position_size_pct - activeStrategy.position_size_pct;

  return [
    {
      label: "入场门槛",
      delta: `${formatSignedNumber(mediumDelta)}M / ${formatSignedNumber(shortDelta)}S`,
      message: entryDelta < 0 ? "更宽松" : entryDelta > 0 ? "更严格" : "持平",
      tone: entryDelta < 0 ? "watch" : entryDelta > 0 ? "steady" : "neutral"
    },
    {
      label: "止损风险",
      delta: formatSignedPercentPoint(stopLossDelta),
      message: stopLossDelta < 0 ? "更稳" : stopLossDelta > 0 ? "更激进" : "持平",
      tone: stopLossDelta < 0 ? "good" : stopLossDelta > 0 ? "watch" : "neutral"
    },
    {
      label: "目标收益",
      delta: formatSignedPercentPoint(targetDelta),
      message: targetDelta > 0 ? "上行更高" : targetDelta < 0 ? "目标降低" : "持平",
      tone: targetDelta > 0 ? "good" : targetDelta < 0 ? "watch" : "neutral"
    },
    {
      label: "持仓周期",
      delta: `${formatSignedNumber(holdingDaysDelta)}d`,
      message: holdingDaysDelta < 0 ? "更快退出" : holdingDaysDelta > 0 ? "更久持有" : "持平",
      tone: holdingDaysDelta < 0 ? "steady" : holdingDaysDelta > 0 ? "watch" : "neutral"
    },
    {
      label: "仓位",
      delta: formatSignedPercentPoint(positionDelta),
      message: positionDelta < 0 ? "敞口降低" : positionDelta > 0 ? "敞口提高" : "持平",
      tone: positionDelta < 0 ? "steady" : positionDelta > 0 ? "watch" : "neutral"
    }
  ];
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

function formatSignedPercentPoint(value: number): string {
  return `${formatSignedNumber(value * 100, 1)}pp`;
}

function formatSignedNumber(value: number, fractionDigits = 0): string {
  const formatted = Math.abs(value).toFixed(fractionDigits);
  if (value > 0) {
    return `+${formatted}`;
  }
  if (value < 0) {
    return `-${formatted}`;
  }
  return fractionDigits ? Number(0).toFixed(fractionDigits) : "0";
}

function formatError(error: unknown): string {
  if (isApiError(error)) {
    return `${error.code}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Research action failed";
}
