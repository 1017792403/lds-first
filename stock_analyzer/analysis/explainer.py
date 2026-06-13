"""选股解释器 — 为每只入选股票生成评分明细和选股理由"""
import numpy as np

def normalize(value, min_val, max_val):
    """将单个值归一化到 0-100"""
    if max_val == min_val:
        return 50.0
    return 100 * (value - min_val) / (max_val - min_val)


def explain_basic_pick(p, all_scores) -> dict:
    """生成 Basic 策略的评分明细和选股理由"""
    details = {}
    reasons = []

    # 涨幅评分
    chg = float(p.get("change_pct", 0))
    if chg > 5:
        details["涨幅得分"] = "高"
        reasons.append(f"当日强势上涨 {chg:+.1f}%")
    elif chg > 2:
        details["涨幅得分"] = "中高"
        reasons.append(f"稳步上涨 {chg:+.1f}%")
    elif chg > 0:
        details["涨幅得分"] = "中"
        reasons.append(f"微涨 {chg:+.1f}%")
    else:
        details["涨幅得分"] = "低"
        reasons.append(f"下跌 {chg:+.1f}%")

    # 相对强度
    rel = float(p.get("rel_strength", p.get("rel_str", 0)))
    if rel > 5:
        details["板块内强度"] = "领涨"
        reasons.append("板块内领涨龙头")
    elif rel > 0:
        details["板块内强度"] = "偏强"
        reasons.append("跑赢板块平均")
    else:
        details["板块内强度"] = "偏弱"
        reasons.append("弱于板块平均")

    # 量比
    vol = float(p.get("vol_ratio", 0))
    if vol > 3:
        details["量能"] = "放巨量"
        reasons.append(f"成交量放大 {vol:.1f} 倍")
    elif vol > 1.5:
        details["量能"] = "放量"
        reasons.append(f"量价配合，量比 {vol:.1f}")
    elif vol > 1:
        details["量能"] = "正常"
    else:
        details["量能"] = "缩量"
        reasons.append(f"缩量上涨需谨慎（量比 {vol:.1f}）")

    # 成交额
    amt = float(p.get("amount", 0))
    if amt > 1e9:
        details["资金关注"] = "高"
    elif amt > 1e8:
        details["资金关注"] = "中"

    # 行业评分
    ind_boost = float(p.get("industry_boost", p.get("boost", 0)))
    if ind_boost > 60:
        details["所属板块评分"] = "强势板块"
        reasons.append("所属板块整体强势")
    elif ind_boost > 40:
        details["所属板块评分"] = "中等板块"

    return {"details": details, "reasons": reasons}


def explain_v2_pick(p, all_scores) -> dict:
    """生成 V2 策略的评分明细和选股理由"""
    details = {}
    reasons = []

    chg = float(p.get("change_pct", 0))
    rel = float(p.get("rel_strength", 0))
    vol = float(p.get("vol_ratio", 0))
    overheat = float(p.get("overheat_penalty", 1.0))
    vol_penalty = float(p.get("vol_penalty", 1.0))
    sector_boost = float(p.get("sector_boost", 1.0))
    moderate = float(p.get("moderate_bonus", 1.0))

    # 涨幅评价
    if 2 <= chg <= 8:
        details["涨幅评价"] = "温和上涨"
        reasons.append(f"涨幅 {chg:+.1f}% 在最佳区间（2-8%）")
        details["温和上涨奖励"] = f"×{moderate:.1f}"
    elif chg > 8:
        details["涨幅评价"] = "偏高"
        reasons.append(f"涨幅 {chg:+.1f}% 偏高")
        if overheat < 1.0:
            details["过热惩罚"] = f"×{overheat:.1f}（扣减权重）"
            reasons.append(f"过热风险，惩罚系数 {overheat:.1f}")
    elif chg < -3:
        details["涨幅评价"] = "下跌"
        reasons.append(f"当日下跌 {chg:+.1f}%")

    # 相对强度
    if rel > 0:
        reasons.append("板块内领涨")
        details["板块内强度"] = f"跑赢 {rel:+.1f}%"
    else:
        details["板块内强度"] = f"跑输 {rel:+.1f}%"

    # 量比
    if vol > 2:
        reasons.append(f"放量 {vol:.1f} 倍确认")
        details["量能"] = f"放量 {vol:.1f}x"
    elif vol < 1.0:
        details["量能"] = f"缩量 {vol:.1f}x"
        reasons.append(f"缩量 {vol:.1f}x，有风险")
        if vol_penalty < 1.0:
            details["缩量惩罚"] = f"×{vol_penalty:.1f}"
    else:
        details["量能"] = f"正常 {vol:.1f}x"

    # 板块加成
    if sector_boost > 1.0:
        details["板块加成"] = f"×{sector_boost:.1f}"
        reasons.append("所属板块排名前 5")

    return {"details": details, "reasons": reasons}


def explain_v3_pick(p) -> dict:
    """生成 V3 策略的评分明细和选股理由"""
    details = {}
    reasons = []

    # 技术面
    tec = float(p.get("tech", p.get("tech_score", 50)))
    macd = float(p.get("macd", 0))
    golden = p.get("golden_cross", p.get("golden", False))
    kdj = float(p.get("kdj_j", 50))
    vs = float(p.get("vol_ratio", p.get("vol_ratio_s", 1.0)))
    slope = float(p.get("slope", 0))
    diverg = int(p.get("divergence", p.get("diverg", 0)))

    details["技术评分"] = f"{tec:.0f}/100"

    if macd > 0:
        details["MACD"] = f"{macd:+.1f}（多头）"
        reasons.append("MACD 处于多头区间")
    else:
        details["MACD"] = f"{macd:+.1f}（空头）"

    if golden:
        reasons.append("MACD 金叉信号")
        details["MACD 金叉"] = "是"

    if 20 <= kdj <= 80:
        details["KDJ"] = f"{kdj:.0f}（正常区间）"
    elif kdj > 100:
        details["KDJ"] = f"{kdj:.0f}（超买⚠️）"
        reasons.append("KDJ 超买，注意回调风险")
    elif kdj < 20:
        details["KDJ"] = f"{kdj:.0f}（超卖）"
        reasons.append("KDJ 超卖，关注反弹机会")

    if 1.5 <= vs <= 3:
        details["量比"] = f"{vs:.1f}x（健康放量）"
        reasons.append("量能适中，上涨健康")
    elif vs < 0.8:
        details["量比"] = f"{vs:.1f}x（缩量）"
        reasons.append("缩量运行")
    else:
        details["量比"] = f"{vs:.1f}x"

    if slope > 0.5:
        details["价格斜率"] = f"{slope:.3f}（上升趋势）"
        reasons.append("短期趋势向上")
    elif slope < -0.5:
        details["价格斜率"] = f"{slope:.3f}（下降趋势）"
        reasons.append("短期趋势向下")

    if diverg == 1:
        reasons.append("量价配合，上涨有支撑")
        details["量价关系"] = "配合"
    elif diverg == -1:
        reasons.append("量价背离⚠️，上涨不可持续")
        details["量价关系"] = "背离⚠️"

    # 事件面
    evt = float(p.get("event", p.get("event_score", 0)))
    if evt > 50:
        details["事件驱动"] = f"{evt:.0f}/100"
        driver = p.get("event_driver", "")
        if driver:
            reasons.append(f"事件驱动: {driver}")

    # 人性面
    psy = float(p.get("psychology", p.get("psychology_score", 50)))
    details["市场情绪"] = f"{psy:.0f}/100"

    return {"details": details, "reasons": reasons}


def explain(p, strategy: str, all_scores=None) -> dict:
    """根据策略类型生成评分明细和理由"""
    if strategy == "v2":
        return explain_v2_pick(p, all_scores)
    elif strategy == "v3":
        return explain_v3_pick(p)
    else:
        return explain_basic_pick(p, all_scores)
