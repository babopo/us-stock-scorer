from statistics import mean
from typing import Any

from stock_scorer.market_data import DailyBar, MarketSnapshot
from stock_scorer.models import FactorScore, StockScoreResponse
from stock_scorer.scoring import classify_medium_term_score, classify_short_term_state, decide_action


def build_score_from_market_snapshot(snapshot: MarketSnapshot) -> StockScoreResponse:
    factors = _build_factor_scores(snapshot)
    medium_score = _weighted_medium_score(factors)
    short_score = _short_term_score(snapshot.daily_bars)
    overheated = _is_overheated(snapshot.daily_bars)
    broken_trend = _is_broken_trend(snapshot.daily_bars)
    medium_label = classify_medium_term_score(medium_score)
    short_label = classify_short_term_state(
        score=short_score,
        overheated=overheated,
        broken_trend=broken_trend,
    )

    return StockScoreResponse(
        ticker=snapshot.ticker,
        company_name=snapshot.company_name,
        last_price=snapshot.last_price,
        medium_term_score=medium_score,
        medium_term_label=medium_label,
        short_term_score=short_score,
        short_term_label=short_label,
        factors=factors,
        decision=decide_action(medium_label, short_label),
        data_as_of=snapshot.data_as_of,
        data_source=snapshot.source,
    )


def _build_factor_scores(snapshot: MarketSnapshot) -> list[FactorScore]:
    overview = snapshot.overview
    return [
        FactorScore(
            name="质量/盈利",
            score=_quality_score(overview),
            evidence=_quality_evidence(overview),
        ),
        FactorScore(
            name="估值",
            score=_valuation_score(overview),
            evidence=_valuation_evidence(overview),
        ),
        FactorScore(
            name="成长与预期",
            score=_growth_score(overview),
            evidence=_growth_evidence(overview),
        ),
        FactorScore(
            name="投资纪律/财务稳健",
            score=_discipline_score(overview),
            evidence=_discipline_evidence(overview),
        ),
        FactorScore(
            name="中期动量与风险",
            score=_momentum_score(snapshot.daily_bars),
            evidence=_momentum_evidence(snapshot.daily_bars),
        ),
    ]


def _weighted_medium_score(factors: list[FactorScore]) -> int:
    weights = [0.25, 0.20, 0.20, 0.15, 0.20]
    return round(sum(factor.score * weight for factor, weight in zip(factors, weights, strict=True)))


def _quality_score(overview: dict[str, Any]) -> int:
    scores = []
    profit_margin = _optional_float(overview.get("ProfitMargin"))
    roe = _optional_float(overview.get("ReturnOnEquityTTM"))
    if profit_margin is not None:
        scores.append(_scale(profit_margin, low=0.02, high=0.35))
    if roe is not None:
        scores.append(_scale(roe, low=0.05, high=0.35))
    return round(mean(scores)) if scores else 50


def _valuation_score(overview: dict[str, Any]) -> int:
    scores = []
    pe = _first_optional_float(overview, "ForwardPE", "PERatio", "FallbackPERatio")
    earnings_yield = _optional_float(overview.get("EarningsYield"))
    fcf_yield = _optional_float(overview.get("FreeCashFlowYield"))
    if pe is not None and pe > 0:
        scores.append(_scale(pe, low=12, high=45, invert=True))
    if earnings_yield is not None:
        scores.append(_scale(earnings_yield, low=0.02, high=0.08))
    if fcf_yield is not None:
        scores.append(_scale(fcf_yield, low=0.00, high=0.06))
    return round(mean(scores)) if scores else 50


def _growth_score(overview: dict[str, Any]) -> int:
    scores = []
    revenue_growth = _optional_float(overview.get("QuarterlyRevenueGrowthYOY"))
    earnings_growth = _optional_float(overview.get("QuarterlyEarningsGrowthYOY"))
    if revenue_growth is not None:
        scores.append(_scale(revenue_growth, low=-0.05, high=0.25))
    if earnings_growth is not None:
        scores.append(_scale(earnings_growth, low=-0.10, high=0.35))
    return round(mean(scores)) if scores else 50


def _discipline_score(overview: dict[str, Any]) -> int:
    scores = []
    debt_to_equity = _optional_float(overview.get("DebtToEquity"))
    interest_coverage = _optional_float(overview.get("InterestCoverage"))
    net_debt_to_ebitda = _optional_float(overview.get("NetDebtToEBITDA"))
    capex_to_revenue = _optional_float(overview.get("CapexToRevenue"))
    sbc_to_revenue = _optional_float(overview.get("StockBasedCompensationToRevenue"))

    if debt_to_equity is not None:
        scores.append(_scale(debt_to_equity, low=0.0, high=2.5, invert=True))
    if interest_coverage is not None:
        scores.append(_scale(interest_coverage, low=2.0, high=25.0))
    if net_debt_to_ebitda is not None:
        scores.append(_scale(net_debt_to_ebitda, low=0.0, high=4.0, invert=True))
    if capex_to_revenue is not None:
        scores.append(_scale(abs(capex_to_revenue), low=0.03, high=0.25, invert=True))
    if sbc_to_revenue is not None:
        scores.append(_scale(sbc_to_revenue, low=0.0, high=0.10, invert=True))
    if scores:
        return round(mean(scores))

    beta = _optional_float(overview.get("Beta"))
    market_cap = _optional_float(overview.get("MarketCapitalization"))
    scores = [60]
    if beta is not None:
        scores.append(_scale(beta, low=0.75, high=1.60, invert=True))
    if market_cap is not None:
        scores.append(80 if market_cap >= 10_000_000_000 else 55)
    return round(mean(scores))


def _momentum_score(bars: list[DailyBar]) -> int:
    adjusted = [bar.adjusted_close for bar in bars]
    latest = adjusted[0]
    sma20 = _sma(adjusted, 20)
    sma50 = _sma(adjusted, 50)
    return_20 = _return(adjusted, 20)

    score = 50
    if sma20 is not None:
        score += 15 if latest >= sma20 else -10
    if sma50 is not None:
        score += 15 if latest >= sma50 else -15
    if sma20 is not None and sma50 is not None:
        score += 10 if sma20 >= sma50 else -10
    if return_20 is not None:
        score += round(return_20 * 100)
    return _clamp(score)


def _short_term_score(bars: list[DailyBar]) -> int:
    adjusted = [bar.adjusted_close for bar in bars]
    latest = adjusted[0]
    sma20 = _sma(adjusted, 20)
    sma50 = _sma(adjusted, 50)
    return_5 = _return(adjusted, 5)
    return_20 = _return(adjusted, 20)

    score = 50
    if sma20 is not None:
        score += 15 if latest >= sma20 else -10
    if sma50 is not None:
        score += 15 if latest >= sma50 else -15
    if sma20 is not None and sma50 is not None:
        score += 10 if sma20 >= sma50 else -10
    if return_5 is not None:
        score += 8 if return_5 > 0 else -5
    if return_20 is not None:
        score += 12 if return_20 > 0 else -8
    if _is_overheated(bars):
        score -= 8
    return _clamp(score)


def _is_overheated(bars: list[DailyBar]) -> bool:
    adjusted = [bar.adjusted_close for bar in bars]
    latest = adjusted[0]
    sma20 = _sma(adjusted, 20)
    return_5 = _return(adjusted, 5)
    return (sma20 is not None and latest / sma20 - 1 > 0.08) or (
        return_5 is not None and return_5 > 0.08
    )


def _is_broken_trend(bars: list[DailyBar]) -> bool:
    adjusted = [bar.adjusted_close for bar in bars]
    latest = adjusted[0]
    sma20 = _sma(adjusted, 20)
    sma50 = _sma(adjusted, 50)
    return (sma50 is not None and latest < sma50 * 0.97) or (
        sma20 is not None and latest < sma20 * 0.94
    )


def _quality_evidence(overview: dict[str, Any]) -> list[str]:
    margin = _optional_float(overview.get("ProfitMargin"))
    if margin is None:
        return ["数据源未返回利润率，质量分使用中性基准。"]
    return [f"利润率约 {margin:.1%}，用于第一阶段盈利质量代理。"]


def _valuation_evidence(overview: dict[str, Any]) -> list[str]:
    pe = _first_optional_float(overview, "ForwardPE", "PERatio", "FallbackPERatio")
    earnings_yield = _optional_float(overview.get("EarningsYield"))
    fcf_yield = _optional_float(overview.get("FreeCashFlowYield"))
    evidence = []
    if pe is not None and pe > 0:
        evidence.append(f"PE/Forward PE 约 {pe:.1f}，低估值给更高分，高估值降权。")
    if earnings_yield is not None:
        evidence.append(f"盈利收益率约 {earnings_yield:.1%}。")
    if fcf_yield is not None:
        evidence.append(f"自由现金流收益率约 {fcf_yield:.1%}。")
    if not evidence:
        return ["数据源未返回有效 PE，估值分使用中性基准。"]
    return evidence


def _growth_evidence(overview: dict[str, Any]) -> list[str]:
    revenue_growth = _optional_float(overview.get("QuarterlyRevenueGrowthYOY"))
    earnings_growth = _optional_float(overview.get("QuarterlyEarningsGrowthYOY"))
    evidence = []
    if revenue_growth is not None:
        evidence.append(f"季度收入同比约 {revenue_growth:.1%}。")
    if earnings_growth is not None:
        evidence.append(f"季度 EPS 同比约 {earnings_growth:.1%}。")
    return evidence or ["数据源未返回增长字段，成长分使用中性基准。"]


def _momentum_evidence(bars: list[DailyBar]) -> list[str]:
    adjusted = [bar.adjusted_close for bar in bars]
    return_20 = _return(adjusted, 20)
    if return_20 is None:
        return ["历史价格不足 20 个交易日，动量分使用可用均线数据。"]
    return [f"近 20 个交易日复权价格涨跌幅约 {return_20:.1%}。"]


def _discipline_evidence(overview: dict[str, Any]) -> list[str]:
    debt_to_equity = _optional_float(overview.get("DebtToEquity"))
    interest_coverage = _optional_float(overview.get("InterestCoverage"))
    net_debt_to_ebitda = _optional_float(overview.get("NetDebtToEBITDA"))
    capex_to_revenue = _optional_float(overview.get("CapexToRevenue"))
    sbc_to_revenue = _optional_float(overview.get("StockBasedCompensationToRevenue"))
    evidence = []
    if net_debt_to_ebitda is not None:
        evidence.append(f"净债务/EBITDA 约 {net_debt_to_ebitda:.1f}x。")
    if debt_to_equity is not None:
        evidence.append(f"债务/股本约 {debt_to_equity:.2f}x。")
    if interest_coverage is not None:
        evidence.append(f"利息覆盖约 {interest_coverage:.1f}x。")
    if capex_to_revenue is not None:
        evidence.append(f"资本开支/收入约 {abs(capex_to_revenue):.1%}。")
    if sbc_to_revenue is not None:
        evidence.append(f"股权激励/收入约 {sbc_to_revenue:.1%}。")
    return evidence or ["数据源未返回资产负债表/现金流代理字段，财务稳健分使用轻量基准。"]


def _optional_float(value: Any) -> float | None:
    if value in (None, "", "None", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_optional_float(overview: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _optional_float(overview.get(key))
        if value is not None:
            return value
    return None


def _scale(value: float, low: float, high: float, invert: bool = False) -> int:
    if high <= low:
        return 50
    ratio = (value - low) / (high - low)
    if invert:
        ratio = 1 - ratio
    return _clamp(round(ratio * 100))


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[:window])


def _return(values: list[float], periods: int) -> float | None:
    if len(values) <= periods or values[periods] == 0:
        return None
    return values[0] / values[periods] - 1


def _clamp(value: int) -> int:
    return max(0, min(100, value))
