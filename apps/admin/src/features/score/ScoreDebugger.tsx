import { useMutation } from "@tanstack/react-query";
import { Activity, AlertTriangle, Play, RefreshCw } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import {
  isApiError,
  type FactorScore,
  type ShortTermLabel,
  type StockScoreResponse,
  type StockScorerClient
} from "@stock-scorer/api-client";

interface ScoreDebuggerProps {
  client: StockScorerClient;
}

interface RadarDimension {
  id: string;
  label: string;
  chartLabel: string;
  score: number;
  evidence: string[];
}

const RADAR_AXIS_DEFINITIONS = [
  {
    id: "quality",
    label: "质量/盈利",
    chartLabel: "质量",
    matches: (name: string) => name.includes("质量") || name.includes("盈利")
  },
  {
    id: "valuation",
    label: "估值",
    chartLabel: "估值",
    matches: (name: string) => name.includes("估值")
  },
  {
    id: "growth",
    label: "成长与预期",
    chartLabel: "成长",
    matches: (name: string) => name.includes("成长") || name.includes("预期")
  },
  {
    id: "discipline",
    label: "投资纪律/财务稳健",
    chartLabel: "财务",
    matches: (name: string) => name.includes("纪律") || name.includes("财务")
  },
  {
    id: "momentum",
    label: "中期动量与风险",
    chartLabel: "动量",
    matches: (name: string) => name.includes("动量") || name.includes("风险")
  }
] satisfies Array<{
  id: string;
  label: string;
  chartLabel: string;
  matches(name: string): boolean;
}>;

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
  const radarDimensions = useMemo(() => (score ? buildRadarDimensions(score) : []), [score]);

  return (
    <section className="workspace-band score-debugger" aria-labelledby="score-debugger-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Stock intelligence</p>
          <h2 id="score-debugger-title">六维评分雷达</h2>
        </div>
        <span className="status-pill">
          <Activity aria-hidden="true" size={16} />
          Live score
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
          生成评分
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
          <div className="score-hero">
            <div className="score-summary">
              <div>
                <span className="mono ticker">{score.ticker}</span>
                <h3>{score.company_name}</h3>
                <p>
                  {score.data_source} · {score.data_as_of}
                  {elapsedMs !== null ? ` · ${elapsedMs}ms` : ""}
                </p>
              </div>
              <div className="score-metrics" aria-label="Score summary">
                <Metric label="中期" value={score.medium_term_score} tone="gold" />
                <Metric label="短线" value={score.short_term_score} tone="blue" />
                <Metric label="现价" value={`$${score.last_price}`} tone="plain" />
              </div>
              <div className="decision-strip">
                <span>结论</span>
                <strong>{formatAction(score.decision.action)}</strong>
                <p>{score.decision.summary}</p>
              </div>
            </div>

            <RadarPanel score={score} dimensions={radarDimensions} />
          </div>

          <div className="debug-grid">
            <div className="panel">
              <h4>维度证据</h4>
              <div className="factor-list">
                {radarDimensions.map((factor) => (
                  <article key={factor.id} className="factor-row">
                    <div>
                      <strong>{factor.label}</strong>
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
              <h4>交易决策</h4>
              <p className="decision-summary">{score.decision.summary}</p>
              <ListBlock title="触发条件" items={score.decision.trigger_conditions} />
              <ListBlock title="失效条件" items={score.decision.invalidation_conditions} />
              <ListBlock title="风险" items={score.decision.risks} />
            </div>
          </div>

          <details className="raw-json">
            <summary>原始响应</summary>
            <pre>{JSON.stringify(score, null, 2)}</pre>
          </details>
        </div>
      ) : (
        <div className="empty-state">输入 ticker 后生成六维评分、交易结论和数据响应。</div>
      )}
    </section>
  );
}

function RadarPanel({ score, dimensions }: { score: StockScoreResponse; dimensions: RadarDimension[] }) {
  return (
    <figure className="radar-panel" aria-labelledby="six-dim-title">
      <figcaption className="radar-heading">
        <span className="chart-label">Six-dimensional profile</span>
        <h3 id="six-dim-title">六维图</h3>
        <p>
          中期 {formatMediumScore(score.medium_term_score)} · 短线 {formatShortTermLabel(score.short_term_label)}
        </p>
      </figcaption>

      <RadarChart ticker={score.ticker} dimensions={dimensions} />

      <div className="dimension-table" role="table" aria-label="六维评分明细">
        {dimensions.map((dimension) => (
          <div className="dimension-row" role="row" key={dimension.id}>
            <span role="cell">{dimension.label}</span>
            <div role="cell" className="dimension-track" aria-hidden="true">
              <span style={{ width: `${dimension.score}%` }} />
            </div>
            <strong role="cell">{dimension.score}</strong>
          </div>
        ))}
      </div>
    </figure>
  );
}

function RadarChart({ ticker, dimensions }: { ticker: string; dimensions: RadarDimension[] }) {
  const size = 340;
  const center = size / 2;
  const radius = 112;
  const levels = [20, 40, 60, 80, 100];
  const axisPoints = dimensions.map((dimension, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / dimensions.length;
    const score = clampScore(dimension.score);
    return {
      ...dimension,
      angle,
      x: center + Math.cos(angle) * radius,
      y: center + Math.sin(angle) * radius,
      labelX: center + Math.cos(angle) * (radius + 32),
      labelY: center + Math.sin(angle) * (radius + 32),
      valueX: center + Math.cos(angle) * radius * (score / 100),
      valueY: center + Math.sin(angle) * radius * (score / 100)
    };
  });
  const polygonPoints = axisPoints.map((point) => `${point.valueX.toFixed(2)},${point.valueY.toFixed(2)}`).join(" ");

  return (
    <svg className="radar-chart" viewBox={`0 0 ${size} ${size}`} role="img" aria-labelledby="radar-chart-title radar-chart-desc">
      <title id="radar-chart-title">{ticker} 六维评分雷达图</title>
      <desc id="radar-chart-desc">展示质量、估值、成长、财务、动量和短线买点六个维度的 0 到 100 分评分。</desc>
      {levels.map((level) => (
        <polygon key={level} points={buildLevelPolygon(level, axisPoints, center, radius)} className="radar-grid" />
      ))}
      {axisPoints.map((point) => (
        <line key={point.id} x1={center} y1={center} x2={point.x} y2={point.y} className="radar-axis" />
      ))}
      <polygon points={polygonPoints} className="radar-fill" />
      <polyline points={`${polygonPoints} ${axisPoints[0]?.valueX.toFixed(2)},${axisPoints[0]?.valueY.toFixed(2)}`} className="radar-line" />
      {axisPoints.map((point) => (
        <g key={`${point.id}-point`}>
          <circle cx={point.valueX} cy={point.valueY} r="4.5" className="radar-dot" />
          <text x={point.labelX} y={point.labelY} textAnchor={textAnchorFor(point.angle)} dominantBaseline="middle" className="radar-label">
            {point.chartLabel}
          </text>
        </g>
      ))}
    </svg>
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

function buildRadarDimensions(score: StockScoreResponse): RadarDimension[] {
  const factorDimensions = RADAR_AXIS_DEFINITIONS.map((definition) => {
    const factor = score.factors.find((candidate) => definition.matches(candidate.name));
    return toRadarDimension(definition.id, definition.label, definition.chartLabel, factor);
  });

  return [
    ...factorDimensions,
    {
      id: "short-term",
      label: "短线买点",
      chartLabel: "买点",
      score: clampScore(score.short_term_score),
      evidence: [`短期状态：${formatShortTermLabel(score.short_term_label)}`]
    }
  ];
}

function toRadarDimension(id: string, label: string, chartLabel: string, factor: FactorScore | undefined): RadarDimension {
  if (!factor) {
    return {
      id,
      label,
      chartLabel,
      score: 50,
      evidence: ["当前响应未返回该维度，图中以中性分展示。"]
    };
  }

  return {
    id,
    label: factor.name,
    chartLabel,
    score: clampScore(factor.score),
    evidence: factor.evidence
  };
}

function buildLevelPolygon(level: number, points: Array<{ angle: number }>, center: number, radius: number): string {
  return points
    .map((point) => {
      const levelRadius = radius * (level / 100);
      const x = center + Math.cos(point.angle) * levelRadius;
      const y = center + Math.sin(point.angle) * levelRadius;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function textAnchorFor(angle: number): "start" | "middle" | "end" {
  const x = Math.cos(angle);
  if (x > 0.25) {
    return "start";
  }
  if (x < -0.25) {
    return "end";
  }
  return "middle";
}

function clampScore(score: number): number {
  return Math.max(0, Math.min(100, Math.round(score)));
}

function formatMediumScore(score: number): string {
  if (score >= 80) {
    return "强势";
  }
  if (score >= 65) {
    return "积极";
  }
  if (score >= 50) {
    return "中性";
  }
  if (score >= 35) {
    return "偏弱";
  }
  return "回避";
}

function formatShortTermLabel(label: ShortTermLabel): string {
  const labels: Record<ShortTermLabel, string> = {
    entry: "可入场",
    probe: "小仓观察",
    wait_pullback: "等回调",
    wait_breakout: "等突破",
    avoid: "回避"
  };
  return labels[label];
}

function formatAction(action: StockScoreResponse["decision"]["action"]): string {
  const labels: Record<StockScoreResponse["decision"]["action"], string> = {
    buy_in_tranches: "分批买入",
    small_probe: "小仓观察",
    wait: "等待确认",
    short_term_only: "仅短线",
    avoid: "回避"
  };
  return labels[action];
}

function formatError(error: unknown): string {
  if (isApiError(error)) {
    return `${error.code}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Request failed";
}
