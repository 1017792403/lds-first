"""股票筛选 — 候选池构建，按事件板块筛选等"""
import pandas as pd
from ..config import EVENT_SECTORS_FULL, EVENT_SECTORS_LITE, CANDIDATES_PER_INDUSTRY


def build_candidate_pool(stock_data: pd.DataFrame,
                         top_industry_codes: list,
                         n_per_industry: int = CANDIDATES_PER_INDUSTRY) -> pd.DataFrame:
    """从指定行业中各取成交额前 N 名作为候选池"""
    pool = []
    for l2 in top_industry_codes:
        sub = stock_data[stock_data["l2_code"] == l2].copy()
        top_n = sub.nlargest(min(n_per_industry, len(sub)), "amount")
        pool.append(top_n)
    return pd.concat(pool) if pool else pd.DataFrame()


def build_event_candidate_pool(stock_data: pd.DataFrame,
                               n_per_industry: int = 3,
                               use_full: bool = True) -> pd.DataFrame:
    """基于事件板块构建候选池"""
    sector_map = EVENT_SECTORS_FULL if use_full else EVENT_SECTORS_LITE
    codes = list(sector_map.keys())

    pool = []
    for l2 in codes:
        sub = stock_data[stock_data["l2_code"] == l2].copy()
        top_n = sub.nlargest(min(n_per_industry, len(sub)), "amount")
        pool.append(top_n)
    return pd.concat(pool) if pool else pd.DataFrame()


def get_event_sector_info(l2_code: str, use_full: bool = True) -> dict:
    """获取事件板块信息"""
    source = EVENT_SECTORS_FULL if use_full else EVENT_SECTORS_LITE
    info = source.get(l2_code)
    if info is None:
        return {"event_score": 30, "exposure_score": 30,
                "driver": "", "psych_note": "", "psych_score": 50}

    if use_full:
        return {
            "event_score": info[0],
            "exposure_score": info[1],
            "driver": info[2],
            "psych_note": info[3],
            "psych_score": info[4],
        }
    else:
        return {
            "event_score": info[0],
            "exposure_score": 50,
            "driver": info[1],
            "psych_note": "",
            "psych_score": 50,
        }
