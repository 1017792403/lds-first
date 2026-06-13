"""评分引擎 — 行业评分 + 个股评分 + 多因子评分"""
import pandas as pd
import numpy as np
from ..config import (
    INDUSTRY_WEIGHTS, STOCK_WEIGHTS, INDUSTRY_BOOST_RATIO,
    MARKET_THRESHOLDS, CANDIDATES_PER_INDUSTRY,
)


def normalize(s: pd.Series) -> pd.Series:
    """Min-Max 归一化到 0-100"""
    mn, mx = s.min(), s.max()
    if mx == mn:
        return pd.Series(50.0, index=s.index)
    return 100 * (s - mn) / (mx - mn)


def score_industries(stock_data: pd.DataFrame) -> pd.DataFrame:
    """行业评分：基于行业平均涨幅、上涨比例、领涨强度、成交额、大涨家数。

    返回按总分降序的 DataFrame: l2_code, ind_name, score, avg_chg, ...
    """
    ind = stock_data.groupby(["l2_code", "ind_name"]).agg(
        stock_count=("stock_code", "nunique"),
        rising_count=("change_pct", lambda x: (x > 0).sum()),
        falling_count=("change_pct", lambda x: (x < 0).sum()),
        avg_chg=("change_pct", "mean"),
        total_amount=("amount", "sum"),
        top3_chg=("change_pct", lambda x: x.nlargest(3).mean()
                  if len(x) >= 3 else x.max()),
        surge_count=("change_pct", lambda x: (x > 5).sum()),
    ).reset_index()

    ind["rise_ratio"] = ind["rising_count"] / ind["stock_count"]

    ind["score"] = (
        normalize(ind["avg_chg"]) * INDUSTRY_WEIGHTS["avg_change"] +
        normalize(ind["rise_ratio"]) * INDUSTRY_WEIGHTS["rise_ratio"] +
        normalize(ind["top3_chg"]) * INDUSTRY_WEIGHTS["top3_change"] +
        normalize(ind["total_amount"]) * INDUSTRY_WEIGHTS["total_amount"] +
        normalize(ind["surge_count"]) * INDUSTRY_WEIGHTS["surge_count"]
    )
    return ind.sort_values("score", ascending=False).reset_index(drop=True)


def get_dynamic_market_m(stock_data: pd.DataFrame) -> int:
    """根据市场状态动态确定 M（入选行业数量）"""
    avg_industry_chg = stock_data.groupby("l2_code")["change_pct"].mean()
    positive_ratio = (avg_industry_chg > 0).mean()

    for _, m in sorted(MARKET_THRESHOLDS.items(),
                               key=lambda x: x[1][0], reverse=True):
        if positive_ratio >= m[0]:
            return m[1]
    return 6


def score_stocks(candidates: pd.DataFrame, industry_scores: pd.DataFrame = None) -> pd.DataFrame:
    """个股评分：结合涨幅、相对强度、量比、成交额。

    如提供 industry_scores，会叠加行业得分加成。
    """
    df = candidates.copy()

    # 板块内相对强度
    ind_avg = df.groupby("l2_code")["change_pct"].transform("mean")
    df["rel_strength"] = df["change_pct"] - ind_avg

    # 量比（相对板块中位数）
    ind_med_amt = df.groupby("l2_code")["amount"].transform("median")
    df["vol_ratio"] = df["amount"] / ind_med_amt.replace(0, 1)

    # 基础评分
    df["raw_score"] = (
        normalize(df["change_pct"]) * STOCK_WEIGHTS["change_pct"] +
        normalize(df["rel_strength"]) * STOCK_WEIGHTS["rel_strength"] +
        normalize(df["vol_ratio"]) * STOCK_WEIGHTS["vol_ratio"] +
        normalize(df["amount"]) * STOCK_WEIGHTS["amount"]
    )

    df["final_score"] = df["raw_score"]

    # 行业得分加成
    if industry_scores is not None and "l2_code" in industry_scores.columns:
        ind_score_map = dict(zip(industry_scores["l2_code"],
                                 industry_scores["score"]))
        df["industry_boost"] = df["l2_code"].map(ind_score_map).fillna(0)
        df["final_score"] = (df["raw_score"] * (1 - INDUSTRY_BOOST_RATIO) +
                             df["industry_boost"] * INDUSTRY_BOOST_RATIO)

    return df.sort_values("final_score", ascending=False).reset_index(drop=True)


def select_top_n(scored: pd.DataFrame, n: int = 10,
                 max_per_industry: int = 3) -> list:
    """从评分结果中选择 Top N，控制单行业最大入选数。"""
    selected = []
    ind_count = {}

    for _, row in scored.iterrows():
        l2 = row.get("l2_code", row.get("industry"))
        if ind_count.get(l2, 0) >= max_per_industry:
            continue
        selected.append(row)
        ind_count[l2] = ind_count.get(l2, 0) + 1
        if len(selected) >= n:
            break

    # 不够 10 只时补选
    if len(selected) < n:
        for _, row in scored.iterrows():
            if len(selected) >= n:
                break
            if not any(row["tc"] == s["tc"] for s in selected):
                selected.append(row)

    return selected


# ============ V2 修正因子 ============

def calc_overheat_penalty(change_pct: float) -> float:
    """过热惩罚：涨幅过高则降低权重"""
    if change_pct > 15:
        return 0.5
    if change_pct > 12:
        return 0.7
    if change_pct > 8:
        return 0.85
    return 1.0


def calc_volume_penalty(vol_ratio: float) -> float:
    """缩量惩罚：量比不足则降低权重"""
    if vol_ratio < 1.0:
        return 0.6
    if vol_ratio < 1.2:
        return 0.8
    return 1.0


def get_sector_boost(l2_code: str, top5_codes: list) -> float:
    """板块强度加成：前 5 行业 1.2x"""
    return 1.2 if l2_code in top5_codes else 1.0


def calc_moderate_bonus(change_pct: float) -> float:
    """温和上涨奖励：2-8% 最佳"""
    if 2 <= change_pct <= 8:
        return 1.3
    if 0 <= change_pct < 2:
        return 1.1
    return 0.8


def score_stocks_v2(candidates: pd.DataFrame,
                    industry_scores: pd.DataFrame = None) -> pd.DataFrame:
    """V2 评分：带过热惩罚 + 缩量惩罚 + 板块加成 + 温和奖励"""
    df = candidates.copy()

    # 基础因子
    ind_avg = df.groupby("l2_code")["change_pct"].transform("mean")
    df["rel_strength"] = df["change_pct"] - ind_avg
    ind_med_amt = df.groupby("l2_code")["amount"].transform("median")
    df["vol_ratio"] = df["amount"] / ind_med_amt.replace(0, 1)

    # V2 修正因子
    df["overheat_penalty"] = df["change_pct"].apply(calc_overheat_penalty)
    df["vol_penalty"] = df["vol_ratio"].apply(calc_volume_penalty)

    if industry_scores is not None:
        top5 = industry_scores.head(5)["l2_code"].tolist()
        df["sector_boost"] = df["l2_code"].apply(
            lambda x: get_sector_boost(x, top5))
    else:
        df["sector_boost"] = 1.0

    df["moderate_bonus"] = df["change_pct"].apply(calc_moderate_bonus)

    # V2 复合评分
    df["raw_score"] = (
        normalize(df["change_pct"]) * 0.20 +
        normalize(df["rel_strength"]) * 0.20 +
        normalize(df["vol_ratio"]) * 0.20 +
        normalize(df["amount"]) * 0.10
    )

    df["final_score"] = (df["raw_score"] * df["overheat_penalty"] *
                         df["vol_penalty"] * df["sector_boost"] *
                         df["moderate_bonus"])

    # 行业得分加成
    if industry_scores is not None:
        ind_score_map = dict(zip(industry_scores["l2_code"],
                                 industry_scores["score"]))
        df["industry_boost"] = df["l2_code"].map(ind_score_map).fillna(0)
        df["final_score"] = (df["final_score"] * 0.7 +
                             df["industry_boost"] * 0.3)

    return df.sort_values("final_score", ascending=False).reset_index(drop=True)
