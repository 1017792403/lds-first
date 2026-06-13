#!/usr/bin/env python3
"""验证复盘数据 — 用 K 线回填每只选股的次日实际涨跌幅

用法：python scripts/verify_review.py
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['PYTHONIOENCODING'] = 'utf-8'

import builtins
_old_print = builtins.print
builtins.print = lambda *a, **k: None

from stock_analyzer.data.loader import load_sw_classification
from stock_analyzer.data.kline import fetch_kline_batch

builtins.print = _old_print


def load_review_data():
    """加载现有的复盘数据"""
    paths = [
        os.path.join(os.getcwd(), "data", "review_history.json"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "review_history.json"),
    ]
    for p in paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return []


def save_review_data(records):
    """保存复盘数据"""
    path = os.path.join(os.getcwd(), "data", "review_history.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(records)} records to {path}", file=sys.__stdout__)


def get_next_trading_day(trading_days, current_date):
    """获取当前日的下一个交易日"""
    sorted_days = sorted(trading_days)
    if current_date in sorted_days:
        idx = sorted_days.index(current_date)
        if idx + 1 < len(sorted_days):
            return sorted_days[idx + 1]
    return None


def main():
    print("Loading review data...", file=sys.__stdout__)
    records = load_review_data()
    if not records:
        print("No review data found!", file=sys.__stdout__)
        return
    print(f"  {len(records)} records loaded", file=sys.__stdout__)

    # 收集所有需要查询的股票代码和日期
    tc_set = set()
    date_pick_map = {}  # {(tc, date): pick_info}
    date_set = set()

    stock_data = load_sw_classification()
    code_to_tc = dict(zip(stock_data["stock_code"], stock_data["tc"]))

    for record in records:
        date = record["date"]
        # Normalize date format: YYYYMMDD -> YYYY-MM-DD
        if len(date) == 8 and "-" not in date:
            date_fmt = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        else:
            date_fmt = date
        date_set.add(date_fmt)

        for pick in record["picks"]:
            code = pick.get("code", "")
            if not code or pick.get("actual_change") is not None:
                continue  # 已回填的跳过
            tc = code_to_tc.get(code)
            if tc:
                tc_set.add(tc)
                date_pick_map[(tc, date_fmt)] = (record, pick)

    print(f"  {len(tc_set)} stocks to query, {len(date_set)} trading days", file=sys.__stdout__)

    if not tc_set:
        print("  All picks already verified or no data", file=sys.__stdout__)
        return

    # 批量拉取 K 线
    print(f"  Fetching klines for {len(tc_set)} stocks...", file=sys.__stdout__)
    kline_data = fetch_kline_batch(list(tc_set), days=60, max_workers=8, interval=0)
    print(f"  Got kline for {len(kline_data)} stocks", file=sys.__stdout__)

    # 获取所有交易日
    all_dates = set()
    for tc, klines in kline_data.items():
        for k in klines:
            if len(k) >= 3:
                all_dates.add(k[0])
    sorted_dates = sorted(all_dates)
    print(f"  {len(sorted_dates)} trading dates available", file=sys.__stdout__)

    # 回填实际涨跌幅
    filled = 0
    for (tc, date_fmt), (record, pick) in date_pick_map.items():
        klines = kline_data.get(tc, [])
        if not klines:
            continue

        # 找当天的收盘价
        day_close = None
        for k in klines:
            if k[0] == date_fmt:
                day_close = float(k[2])
                break
        if day_close is None:
            continue

        # 找次日的收盘价
        next_date = get_next_trading_day(sorted_dates, date_fmt)
        if next_date is None:
            continue

        next_close = None
        for k in klines:
            if k[0] == next_date:
                next_close = float(k[2])
                break
        if next_close is None:
            continue

        # 计算实际涨跌幅
        actual_change = round((next_close / day_close - 1) * 100, 2)

        # 判断方向是否正确
        predicted_up = pick["predicted_change"] > 0
        actual_up = actual_change > 0
        hit = predicted_up == actual_up

        pick["actual_change"] = actual_change
        pick["hit"] = hit
        filled += 1

    # 保存
    save_review_data(records)
    print(f"  Filled {filled} picks with actual data", file=sys.__stdout__)

    # 统计胜率
    total = sum(1 for r in records for p in r["picks"] if p["hit"] is not None)
    hits = sum(1 for r in records for p in r["picks"] if p["hit"] is True)
    if total > 0:
        print(f"\n  Overall hit rate: {hits}/{total} = {hits/total*100:.1f}%", file=sys.__stdout__)

        # 按策略统计
        for strategy in ["basic", "v2", "v3"]:
            s_total = sum(1 for r in records if r["strategy"] == strategy for p in r["picks"] if p["hit"] is not None)
            s_hits = sum(1 for r in records if r["strategy"] == strategy for p in r["picks"] if p["hit"] is True)
            if s_total > 0:
                print(f"  {strategy}: {s_hits}/{s_total} = {s_hits/s_total*100:.1f}%", file=sys.__stdout__)


if __name__ == "__main__":
    main()
