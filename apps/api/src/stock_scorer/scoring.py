from stock_scorer.models import ActionDecision, Decision, HorizonLabel, ShortTermLabel


def classify_medium_term_score(score: int) -> HorizonLabel:
    if score >= 80:
        return HorizonLabel.STRONG
    if score >= 65:
        return HorizonLabel.POSITIVE
    if score >= 50:
        return HorizonLabel.NEUTRAL
    if score >= 35:
        return HorizonLabel.WEAK
    return HorizonLabel.AVOID


def classify_short_term_state(score: int, overheated: bool, broken_trend: bool) -> ShortTermLabel:
    if broken_trend:
        return ShortTermLabel.AVOID
    if overheated:
        return ShortTermLabel.WAIT_PULLBACK
    if score >= 75:
        return ShortTermLabel.ENTRY
    if score >= 60:
        return ShortTermLabel.PROBE
    if score >= 45:
        return ShortTermLabel.WAIT_BREAKOUT
    return ShortTermLabel.AVOID


def decide_action(medium: HorizonLabel, short: ShortTermLabel) -> Decision:
    if medium in {HorizonLabel.STRONG, HorizonLabel.POSITIVE} and short == ShortTermLabel.ENTRY:
        return Decision(
            action=ActionDecision.BUY_IN_TRANCHES,
            summary="中长期质量较强，短期买点也确认，适合分批买入。",
            trigger_conditions=["短期趋势保持在 20 日均线上方", "相对 SPY 或 QQQ 维持强势"],
            invalidation_conditions=["跌破 50 日均线后无法快速收复", "下一次财报后盈利预期明显下修"],
            risks=["单只股票波动可能显著高于指数", "若大盘转弱，短期信号可靠性下降"],
        )
    if medium in {HorizonLabel.STRONG, HorizonLabel.POSITIVE} and short == ShortTermLabel.WAIT_PULLBACK:
        return Decision(
            action=ActionDecision.WAIT,
            summary="好公司但短期偏热，不追高，等待回调或新的突破确认。",
            trigger_conditions=["回踩 20 日均线附近企稳", "放量突破最近压力位"],
            invalidation_conditions=["跌破 50 日均线且相对强弱转弱", "基本面预期下修"],
            risks=["短期涨幅过大后可能出现估值压缩", "事件窗口可能放大波动"],
        )
    if medium in {HorizonLabel.WEAK, HorizonLabel.AVOID} and short in {ShortTermLabel.ENTRY, ShortTermLabel.PROBE}:
        return Decision(
            action=ActionDecision.SHORT_TERM_ONLY,
            summary="短期信号可交易，但中长期质量不足，只适合短线观察，不进入长期仓位。",
            trigger_conditions=["短期趋势继续保持强势", "成交量支持突破"],
            invalidation_conditions=["跌回突破位下方", "放量下跌并跌破 20 日均线"],
            risks=["基本面较弱会降低反弹延续性", "不适合扩大为长期仓位"],
        )
    if short == ShortTermLabel.PROBE and medium == HorizonLabel.NEUTRAL:
        return Decision(
            action=ActionDecision.SMALL_PROBE,
            summary="中长期中性，短期条件尚可，可以小仓观察。",
            trigger_conditions=["价格站稳 20 日均线", "行业 ETF 同步走强"],
            invalidation_conditions=["跌破最近 swing low", "短期相对强弱转负"],
            risks=["缺少中长期安全边际", "仓位应控制在观察级别"],
        )
    if short == ShortTermLabel.WAIT_BREAKOUT:
        return Decision(
            action=ActionDecision.WAIT,
            summary="方向未确认，等待突破或回踩确认。",
            trigger_conditions=["放量突破压力位", "回踩支撑后重新转强"],
            invalidation_conditions=["横盘后向下破位", "行业相对强弱恶化"],
            risks=["震荡区间内容易出现假突破", "短线交易成本会侵蚀收益"],
        )
    return Decision(
        action=ActionDecision.AVOID,
        summary="中长期或短期条件不足，当前回避。",
        trigger_conditions=["评分重新回到中性以上", "趋势重新站回关键均线"],
        invalidation_conditions=["继续放量下跌", "基本面或行业景气度继续恶化"],
        risks=["弱势股票的反弹持续性较差", "当前不具备清晰风险回报"],
    )
