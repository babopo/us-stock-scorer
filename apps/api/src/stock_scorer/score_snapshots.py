from dataclasses import asdict, dataclass
from typing import Any

from stock_scorer.live_scoring import build_score_from_market_snapshot
from stock_scorer.market_data import DailyBar, MarketSnapshot
from stock_scorer.research_store import get_historical_bars, upsert_score_snapshot


@dataclass(frozen=True)
class ScoreSnapshotGenerationResult:
    ticker: str
    generated_count: int
    latest_date: str | None


def generate_score_snapshots(
    connection: object,
    *,
    ticker: str,
    source: str,
    overview: dict[str, Any],
    company_name: str,
    end_date: str,
) -> ScoreSnapshotGenerationResult:
    bars = get_historical_bars(connection, ticker, None, end_date)
    generated = 0
    latest_date: str | None = None
    for index, bar in enumerate(bars):
        as_of_bars = bars[: index + 1]
        if len(as_of_bars) < 50:
            continue
        score = build_score_from_market_snapshot(
            MarketSnapshot(
                ticker=ticker.upper(),
                company_name=company_name,
                last_price=bar.adjusted_close,
                data_as_of=bar.date,
                daily_bars=sorted(as_of_bars, key=lambda candidate: candidate.date, reverse=True),
                overview=overview,
                source=source,
            )
        )
        upsert_score_snapshot(
            connection,
            ticker=ticker,
            date=bar.date,
            source=source,
            score=score.model_dump(mode="json"),
            input_snapshot={
                "ticker": ticker.upper(),
                "source": source,
                "daily_bar_count": len(as_of_bars),
                "latest_bar": asdict(bar),
                "overview": overview,
            },
        )
        generated += 1
        latest_date = bar.date
    return ScoreSnapshotGenerationResult(ticker=ticker.upper(), generated_count=generated, latest_date=latest_date)

