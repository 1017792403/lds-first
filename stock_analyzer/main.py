#!/usr/bin/env python3
"""stock_analyzer — 股票量化分析主入口

支持的策略模式:
  basic    经典行业+个股评分（对应原始 pipeline）
  v2       过热修正版（对应 pipeline_v2）
  v3       事件驱动多因子（对应 pipeline_v3）

用法:
  python -m stock_analyzer.main basic
  python -m stock_analyzer.main v2
  python -m stock_analyzer.main v3
"""
import io
import sys
import time
import pandas as pd

# 强制 UTF-8 输出
for s in [sys.stdout, sys.stderr]:
    try:
        s.reconfigure(encoding='utf-8')
    except Exception:
        pass

from .config import (
    SW_XLS, RESULT_JSON, CANDIDATES_PER_INDUSTRY,
    TOP_N_FINAL, MAX_PER_INDUSTRY,
)
from .data.loader import load_sw_classification
from .data.fetcher import fetch_quotes
from .data.kline import fetch_kline_batch
from .analysis.scorer import (
    score_industries, get_dynamic_market_m,
    score_stocks, score_stocks_v2, select_top_n,
)
from .analysis.screener import (
    build_candidate_pool, build_event_candidate_pool,
    get_event_sector_info,
)
from .analysis.indicators import calc_all_indicators
from .output.reporter import (
    print_header, print_market_summary,
    print_industry_scores, print_picks, print_summary_table,
)
from .output.exporter import export_to_json


def progress_callback(current: int, total: int):
    """进度回调"""
    if current % 200 == 0 or current == total:
        print(f"  Progress: {current}/{total}", flush=True)


# ========================================================================
# STRATEGY: basic — 经典行业+个股评分
# ========================================================================
def run_basic():
    """经典模式：行业评分 → 个股评分 → Top10"""
    print("=" * 60)
    print("  STOCK ANALYZER — BASIC MODEL")
    print("=" * 60)

    print("\n[1/4] Loading industry classification...")
    stock_data = load_sw_classification()
    print(f"  Loaded {len(stock_data)} stocks, "
          f"{stock_data['l2_code'].nunique()} industries")

    print("\n[2/4] Fetching real-time quotes...")
    quotes = fetch_quotes(
        stock_data["tc"].unique().tolist(),
        progress_cb=progress_callback,
    )
    print(f"  Got {len(quotes)} quotes")

    # Merge
    stock = stock_data.merge(quotes, on="tc", how="inner")
    print(f"  Merged: {len(stock)} stocks")

    print("\n[3/4] Scoring industries...")
    ind_scores = score_industries(stock)
    M = get_dynamic_market_m(stock)
    top_industries = ind_scores.head(M)
    print_industry_scores(top_industries)

    print("\n[4/4] Scoring stocks & selecting top picks...")
    top_codes = top_industries["l2_code"].tolist()
    candidates = build_candidate_pool(stock, top_codes, CANDIDATES_PER_INDUSTRY)
    print(f"  Candidate pool: {len(candidates)} stocks")

    scored = score_stocks(candidates, ind_scores)
    selected = select_top_n(scored, TOP_N_FINAL, MAX_PER_INDUSTRY)

    # Output
    print_picks(selected)

    rising = int((stock["change_pct"] > 0).sum())
    pos_ind = int((ind_scores["avg_chg"] > 0).sum())
    print_market_summary(len(stock), rising, pos_ind, len(ind_scores))

    market_info = {
        "stock_count": len(stock),
        "positive_ratio": round(pos_ind / len(ind_scores), 2),
    }
    export_to_json(selected, market_info, "basic")

    return selected


# ========================================================================
# STRATEGY: v2 — 过热修正版
# ========================================================================
def run_v2():
    """V2 模式：带过热惩罚 + 缩量惩罚 + 板块加成"""
    print("=" * 60)
    print("  STOCK ANALYZER — V2 CORRECTED MODEL")
    print("=" * 60)

    print("\n[1/4] Loading industry classification...")
    stock_data = load_sw_classification()
    print(f"  Loaded {len(stock_data)} stocks")

    print("\n[2/4] Fetching real-time quotes...")
    quotes = fetch_quotes(
        stock_data["tc"].unique().tolist(),
        progress_cb=progress_callback,
    )
    stock = stock_data.merge(quotes, on="tc", how="inner")
    print(f"  Merged: {len(stock)} stocks")

    print("\n[3/4] Scoring industries...")
    ind_scores = score_industries(stock)
    M = get_dynamic_market_m(stock)
    top_industries = ind_scores.head(M)
    print_industry_scores(top_industries)

    print("\n[4/4] V2 scoring with correction factors...")
    top_codes = top_industries["l2_code"].tolist()
    candidates = build_candidate_pool(stock, top_codes, CANDIDATES_PER_INDUSTRY)

    scored = score_stocks_v2(candidates, ind_scores)
    selected = select_top_n(scored, TOP_N_FINAL, MAX_PER_INDUSTRY)

    print_picks(selected)

    rising = int((stock["change_pct"] > 0).sum())
    pos_ind = int((ind_scores["avg_chg"] > 0).sum())
    print_market_summary(len(stock), rising, pos_ind, len(ind_scores))

    market_info = {
        "stock_count": len(stock),
        "positive_ratio": round(pos_ind / len(ind_scores), 2),
    }
    export_to_json(selected, market_info, "v2_corrected")

    return selected


# ========================================================================
# STRATEGY: v3 — 事件驱动多因子
# ========================================================================
def run_v3():
    """V3 模式：事件 + 技术 + 人性 三因子"""
    print("=" * 75)
    print("  STOCK ANALYZER — V3 MULTI-FACTOR (事件+技术+人性)")
    print("=" * 75)

    print("\n[1/5] Loading industry classification...")
    stock_data = load_sw_classification()
    print(f"  Loaded {len(stock_data)} stocks")

    print("\n[2/5] Fetching quotes...")
    quotes = fetch_quotes(
        stock_data["tc"].unique().tolist(),
        progress_cb=progress_callback,
    )
    stock = stock_data.merge(quotes, on="tc", how="inner")
    print(f"  Merged: {len(stock)} stocks")

    print("\n[3/5] Building event-driven candidate pool...")
    candidates = build_event_candidate_pool(stock, n_per_industry=3, use_full=True)
    print(f"  {len(candidates)} candidates for kline analysis")

    print("\n[4/5] Fetching kline & computing technical indicators...")
    tc_list = candidates["tc"].unique().tolist()
    kline_data = fetch_kline_batch(tc_list)
    print(f"  Got kline for {len(kline_data)} stocks")

    # 评分流程
    print("\n[5/5] Scoring with multi-factor model...")
    results = []
    for _, s in candidates.iterrows():
        tc = s["tc"]
        l2c = s["l2_code"]
        klines = kline_data.get(tc, [])
        ind = calc_all_indicators(klines)
        ei = get_event_sector_info(l2c, use_full=True)
        chg = float(s["change_pct"])

        # 技术评分 (40%)
        tec = _calc_tech_score(ind)
        # 人性评分 (30%)
        psi = _calc_psychology_score(ei["psych_score"], chg, ind)

        final = tec * 0.40 + ei["event_score"] * 0.20 + ei["exposure_score"] * 0.10 + psi * 0.30
        est = _calc_estimated(chg, tec, psi, ind)
        prob = min(40 + final * 0.35, 80)

        logic = _build_v3_logic(ei["driver"], ind)

        results.append({
            "tc": tc, "code": s["stock_code"], "name": s["name"],
            "industry": s["ind_name"], "l2_code": l2c,
            "price": float(s["price"]), "change_pct": chg,
            "final": round(final, 1), "tech": tec,
            "event": ei["event_score"], "exposure": ei["exposure_score"],
            "psychology": psi, "macd": ind.get("macd", 0),
            "golden_cross": ind.get("golden_cross", False),
            "kdj_j": ind.get("kdj_j", 50),
            "vol_ratio": ind.get("vol_ratio_s", 1.0),
            "slope": ind.get("slope", 0),
            "divergence": ind.get("divergence", 0),
            "est": round(est, 1), "prob": round(prob),
            "event_driver": ei["driver"],
            "logic": "; ".join(logic),
        })

    results.sort(key=lambda x: x["final"], reverse=True)
    selected = select_top_n(
        pd.DataFrame(results), TOP_N_FINAL, MAX_PER_INDUSTRY)

    # Output
    print_picks(selected, "V3 MULTI-FACTOR: 事件+技术+人性")

    market_info = {
        "stock_count": len(stock),
        "positive_ratio": 0,
        "event_analysis": [
            "1.SpaceX史上最大IPO→商业航天板块直接利好",
            "2.长鑫科技IPO获证监会注册批准→半导体利好",
            "3.存储龙头大举扩产→半导体设备需求",
            "4.沪指放量6600亿涨超1%→情绪高涨",
        ],
    }
    export_to_json(selected, market_info, "v3_multi_factor")

    return selected


# ============ V3 辅助函数 ============

def _calc_tech_score(ind: dict) -> int:
    """计算技术评分 (0-100)"""
    if not ind:
        return 50
    tec = 50
    if ind.get("macd", 0) > 0:
        tec += 15
    if ind.get("hist", 0) > 0:
        tec += 10
    if ind.get("golden_cross", False):
        tec += 20
    kdj = ind.get("kdj_j", 50)
    if 20 <= kdj <= 80:
        tec += 10
    elif kdj > 100:
        tec -= 20
    elif kdj > 80:
        tec -= 10
    vs = ind.get("vol_ratio_s", 1.0)
    if 1.5 <= vs <= 3:
        tec += 15
    elif vs < 0.8:
        tec -= 10
    if ind.get("slope", 0) > 0.5:
        tec += 10
    elif ind.get("slope", 0) < -0.5:
        tec -= 15
    dv = ind.get("divergence", 0)
    if dv == 1:
        tec += 15
    elif dv == -1:
        tec -= 20
    return max(0, min(100, tec))


def _calc_psychology_score(base_psych: float, chg: float, ind: dict) -> int:
    """计算人性评分 (0-100)"""
    psi = base_psych
    if chg > 15:
        psi -= 20
    elif chg > 10:
        psi -= 8
    kdj = ind.get("kdj_j", 50)
    vs = ind.get("vol_ratio_s", 1.0)
    if 3 <= chg <= 10 and 1.5 <= vs <= 3:
        psi += 15
    if kdj > 90:
        psi -= 10
    if ind.get("divergence", 0) == -1:
        psi -= 15
    return max(0, min(100, psi))


def _calc_estimated(chg: float, tec: int, psi: int, ind: dict) -> float:
    """估算预期涨幅"""
    est = max(abs(chg) * 0.3 + 1.5, 2)
    if tec > 70 and psi > 60:
        est *= 1.3
    kdj = ind.get("kdj_j", 50)
    if kdj > 90 or ind.get("divergence", 0) == -1:
        est *= 0.7
    if ind.get("golden_cross", False):
        est *= 1.2
    return est


def _build_v3_logic(driver: str, ind: dict) -> list:
    """构建 V3 选股逻辑描述"""
    parts = [f"事件:{driver}"]
    if ind.get("golden_cross", False):
        parts.append("MACD金叉")
    kdj = ind.get("kdj_j", 50)
    if 20 < kdj < 80:
        parts.append(f"KDJ{kdj:.0f}健康")
    elif kdj > 100:
        parts.append(f"KDJ{kdj:.0f}超买")
    if ind.get("divergence", 0) == 1:
        parts.append("量价配合")
    elif ind.get("divergence", 0) == -1:
        parts.append("量价背离")
    vs = ind.get("vol_ratio_s", 1.0)
    if vs > 1.5:
        parts.append(f"放量{vs:.1f}倍")
    return parts


# ========================================================================
# CLI ENTRY POINT
# ========================================================================
MODES = {
    "basic": run_basic,
    "v2": run_v2,
    "v3": run_v3,
}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "basic"
    if mode in MODES:
        t0 = time.time()
        MODES[mode]()
        print(f"\n⏱  Done in {time.time() - t0:.1f}s", flush=True)
    else:
        print(f"Unknown mode: {mode}")
        print(f"Available: {', '.join(MODES.keys())}")
        sys.exit(1)


if __name__ == "__main__":
    main()
