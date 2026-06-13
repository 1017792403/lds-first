#!/usr/bin/env python3
"""历史回填脚本 — 用腾讯 K 线数据回填近一个月选股记录

用法：python scripts/backfill_history.py
"""
import os
import sys
import json
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 抑制 print
import builtins
_old_print = builtins.print
builtins.print = lambda *a, **k: None

from stock_analyzer.data.loader import load_sw_classification
from stock_analyzer.data.kline import fetch_kline
from stock_analyzer.analysis.scorer import (
    score_industries, get_dynamic_market_m,
    score_stocks, score_stocks_v2, select_top_n,
    normalize
)
from stock_analyzer.analysis.screener import build_candidate_pool
from stock_analyzer.analysis.indicators import calc_all_indicators
from stock_analyzer.review import record_picks
from stock_analyzer.config import CANDIDATES_PER_INDUSTRY, TOP_N_FINAL, MAX_PER_INDUSTRY
from stock_analyzer.analysis.screener import build_event_candidate_pool, get_event_sector_info

builtins.print = _old_print

DAYS = 60  # 拉取 60 天 K 线
TRADING_DAYS_BACK = 30  # 回填 30 个交易日


def progress(msg):
    print(f"  {msg}", file=sys.__stdout__)


def get_trading_days(kline_data):
    """从 K 线数据中提取所有交易日"""
    all_dates = set()
    for tc, klines in kline_data.items():
        for k in klines:
            if len(k) >= 3:
                all_dates.add(k[0])
    return sorted(all_dates, reverse=True)[:TRADING_DAYS_BACK]


def build_daily_snapshot(stock_data, kline_data, target_date):
    """为指定日期构建行情快照"""
    records = []
    for _, stock in stock_data.iterrows():
        tc = stock["tc"]
        klines = kline_data.get(tc, [])
        if not klines:
            continue
        # 找到目标日期或最近的前一个日期
        daily_data = None
        for k in klines:
            if k[0] == target_date:
                daily_data = k
                break
        if daily_data is None:
            continue
        
        close = float(daily_data[2])
        open_p = float(daily_data[1])
        change_pct = round((close / open_p - 1) * 100, 2) if open_p > 0 else 0
        volume = float(daily_data[5]) if len(daily_data) > 5 else 0
        amount = volume * close  # 近似成交额
        
        records.append({
            "stock_code": stock["stock_code"],
            "name": stock.get("ind_name", ""),
            "industry_code": stock.get("industry_code", ""),
            "l2_code": stock["l2_code"],
            "ind_name": stock["ind_name"],
            "tc": tc,
            "price": close,
            "change_pct": change_pct,
            "volume": volume,
            "amount": amount,
        })
    
    return pd.DataFrame(records)


def run_strategy_for_date(df, strategy, target_date):
    """在指定日期运行指定策略"""
    if df.empty or len(df) < 50:
        return []
    
    if strategy == "v3":
        # V3: 事件驱动 + 技术面
        return _run_v3_for_date(df, target_date)
    
    # Basic / V2: 行业评分 + 个股评分
    ind_scores = score_industries(df)
    if ind_scores.empty:
        return []
    M = get_dynamic_market_m(df)
    top_ind = ind_scores.head(M)
    top_codes = top_ind["l2_code"].tolist()
    candidates = build_candidate_pool(df, top_codes, CANDIDATES_PER_INDUSTRY)
    if candidates.empty:
        return []
    
    if strategy == "basic":
        scored = score_stocks(candidates, ind_scores)
    else:
        scored = score_stocks_v2(candidates, ind_scores)
    
    return select_top_n(scored, TOP_N_FINAL, MAX_PER_INDUSTRY)


def _run_v3_for_date(df, target_date):
    """V3 策略用当前 K 线判断技术指标"""
    candidates = build_event_candidate_pool(df, n_per_industry=3, use_full=True)
    if candidates.empty:
        return []
    
    results = []
    for _, s in candidates.iterrows():
        tc = s["tc"]
        l2c = s["l2_code"]
        # 获取到目标日期为止的 K 线
        klines = fetch_kline(tc, DAYS)
        if not klines:
            continue
        # 截取到目标日期
        klines = [k for k in klines if k[0] <= target_date]
        if len(klines) < 10:
            continue
        
        ind = calc_all_indicators(klines)
        ei = get_event_sector_info(l2c, use_full=True)
        chg = float(s["change_pct"])
        
        tec = 50
        if ind.get("macd", 0) > 0: tec += 15
        if ind.get("golden_cross", False): tec += 20
        kdj = ind.get("kdj_j", 50)
        if 20 <= kdj <= 80: tec += 10
        elif kdj > 100: tec -= 20
        vs = ind.get("vol_ratio_s", 1.0)
        if 1.5 <= vs <= 3: tec += 15
        dv = ind.get("divergence", 0)
        if dv == 1: tec += 15
        elif dv == -1: tec -= 20
        tec = max(0, min(100, tec))
        
        psi = ei["psych_score"]
        if 3 <= chg <= 10 and 1.5 <= vs <= 3: psi += 15
        if kdj > 90: psi -= 10
        psi = max(0, min(100, psi))
        
        final = tec * 0.40 + ei["event_score"] * 0.20 + ei["exposure_score"] * 0.10 + psi * 0.30
        
        results.append({
            "tc": tc, "code": s["stock_code"], "name": s["name"],
            "industry": s["ind_name"], "l2_code": l2c,
            "price": float(s["price"]), "change_pct": chg,
            "final_score": round(final, 1), "final": round(final, 1),
        })
    
    results.sort(key=lambda x: x["final"], reverse=True)
    return results[:TOP_N_FINAL]


def main():
    progress("Loading industry classification...")
    stock_data = load_sw_classification()
    progress(f"  {len(stock_data)} stocks")
    
    # 取候选股票（各行业成交额前列的）
    tc_list = stock_data["tc"].unique().tolist()
    progress(f"Fetching {DAYS}-day kline for {len(tc_list)} stocks...")
    
    # 分批获取 K 线
    kline_data = {}
    batch_size = 100
    for i in range(0, len(tc_list), batch_size):
        batch = tc_list[i:i+batch_size]
        for tc in batch:
            klines = fetch_kline(tc, DAYS)
            if klines:
                kline_data[tc] = klines
        progress(f"  {min(i+batch_size, len(tc_list))}/{len(tc_list)} ({len(kline_data)} with data)")
        time.sleep(0.05)
    
    progress(f"Got kline for {len(kline_data)} stocks")
    
    # 获取交易日列表
    trading_days = get_trading_days(kline_data)
    progress(f"Found {len(trading_days)} trading days")
    
    if not trading_days:
        progress("No trading days found!")
        return
    
    # 对于每个交易日，运行三种策略
    total = 0
    for day_idx, target_date in enumerate(trading_days):
        date_str = target_date.replace("-", "")
        progress(f"\n[{day_idx+1}/{len(trading_days)}] {target_date}")
        
        daily_df = build_daily_snapshot(stock_data, kline_data, target_date)
        if daily_df.empty:
            progress(f"  No data for {target_date}")
            continue
        
        for mode in ['basic', 'v2', 'v3']:
            picks = run_strategy_for_date(daily_df, mode, target_date)
            if picks:
                _old_print(f"  {mode}: {len(picks)} picks", file=sys.__stdout__)
                record_picks(picks, mode, date=date_str)
                total += 1
            time.sleep(0.1)
    
    _old_print(f"\nDone! Recorded {total} strategy runs across {len(trading_days)} trading days.", file=sys.__stdout__)


if __name__ == "__main__":
    main()
