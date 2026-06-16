"""复盘模块 — 每日选股追踪 + 胜率统计

记录每日选股结果 → 次日自动拉取实际涨跌幅 → 按行业/策略维度统计胜率。
"""
import os
import json
from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd
import numpy as np
from ..config import TEMP

REVIEW_DB = os.path.join(TEMP, "review_history.json")
REVIEW_LOG = os.path.join(TEMP, "review_log.json")


def _load_history() -> list:
    """加载历史复盘记录，优先项目 data/ 目录"""
    paths = [
        os.path.join(os.getcwd(), "data", "review_history.json"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "review_history.json"),
        REVIEW_DB,
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                records = json.load(f)
            if len(records) >= 10:  # 取数据最全的那个
                return records
            # 否则继续找更大的
    # 最后返回 TEMP 目录的（如果有）
    if os.path.exists(REVIEW_DB):
        with open(REVIEW_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_history(records: list):
    """保存历史复盘记录"""
    with open(REVIEW_DB, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def record_picks(picks: list, strategy: str = "basic",
                 date: str = None) -> dict:
    """记录当日选股结果"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    record = {
        "date": date,
        "strategy": strategy,
        "picks_count": len(picks),
        "picks": [],
        "created_at": datetime.now().isoformat(),
    }

    for p in picks:
        record["picks"].append({
            "code": p.get("code", p.get("stock_code", "")),
            "name": p.get("name", "?"),
            "industry": p.get("industry", p.get("ind_name", "")),
            "predicted_score": float(p.get("score", p.get("final", 0))),
            "predicted_change": float(p.get("change_pct", p.get("chg", 0))),
            "actual_change": None,  # 待回填
            "hit": None,            # 待计算
        })

    history = _load_history()
    # dedup: same date+strategy overwrites
    history = [r for r in history if not (r["date"] == date and r["strategy"] == strategy)]
    history.append(record)
    _save_history(history)
    print(f"  Recorded {len(picks)} picks for {date} ({strategy})")
    return record


def update_actuals(date: str, actual_data: dict):
    """回填实际涨跌幅

    actual_data: {"000001": 1.23, ...}  code → change_pct
    """
    history = _load_history()
    updated = 0

    for record in history:
        if record["date"] != date:
            continue
        for pick in record["picks"]:
            code = pick["code"]
            if code in actual_data:
                pick["actual_change"] = actual_data[code]
                pick["hit"] = (actual_data[code] > 0) == (pick["predicted_change"] > 0)
                updated += 1

    if updated:
        _save_history(history)
        print(f" Updated {updated} picks for {date}")
    return updated


def fetch_and_update_actuals(date: str = None):
    """自动拉取实际行情并更新"""
    if date is None:
        date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # 读取当日记录中的股票代码
    history = _load_history()
    codes = set()
    for record in history:
        if record["date"] == date:
            codes.update(p["code"] for p in record["picks"])

    if not codes:
        print(f"  No records found for {date}")
        return 0

    # 拉取实时行情
    from ..data.fetcher import fetch_quotes
    from ..data.loader import _to_tencent_code

    tc_list = [_to_tencent_code(c) for c in codes]
    quotes = fetch_quotes(tc_list, use_cache=False)

    # 构建代码→涨幅映射
    actual_data = {}
    for _, row in quotes.iterrows():
        code = row["tc"][2:]  # 去掉 sh/sz 前缀
        actual_data[code] = float(row["change_pct"])

    return update_actuals(date, actual_data)


def get_stats(strategy: str = None) -> dict:
    """获取统计数据"""
    history = _load_history()
    if not history:
        return {"total_sessions": 0, "total_picks": 0}

    # 过滤策略
    if strategy:
        history = [r for r in history if r["strategy"] == strategy]

    # 统计所有推荐和已验证的
    all_picks = []
    verified_picks = []
    for record in history:
        for p in record["picks"]:
            all_picks.append(p)
            if p["hit"] is not None:
                verified_picks.append(p)

    total = len(all_picks)
    verified_total = len(verified_picks)
    hits = sum(1 for p in verified_picks if p["hit"])
    hit_rate = hits / verified_total if verified_total > 0 else 0

    # 平均涨幅（只算已验证的）
    actuals = [p["actual_change"] for p in verified_picks
               if p["actual_change"] is not None]
    avg_actual = np.mean(actuals) if actuals else 0

    return {
        "total_sessions": len(history),
        "total_picks": total,
        "verified_picks": verified_total,
        "hits": hits,
        "hit_rate": round(hit_rate * 100, 1),
        "avg_actual_change": round(avg_actual, 2),
        "strategies": list(set(r["strategy"] for r in history)),
    }


def get_stock_stats() -> list:
    """按股票代码聚合，返回每只股票的统计数据（选中次数、胜率、平均涨幅等）"""
    history = _load_history()
    stock_map = {}

    for record in history:
        date = record["date"]
        strategy = record["strategy"]
        for pick in record["picks"]:
            code = pick.get("code", "")
            if not code:
                continue
            if code not in stock_map:
                stock_map[code] = {
                    "code": code,
                    "name": pick.get("name", "?"),
                    "industry": pick.get("industry", "?"),
                    "picked_count": 0,
                    "wins": 0,
                    "losses": 0,
                    "no_data": 0,
                    "total_score": 0.0,
                    "total_predicted_change": 0.0,
                    "total_actual_change": 0.0,
                    "actual_count": 0,
                    "last_picked": date,
                    "first_picked": date,
                    "picks": [],
                }

            s = stock_map[code]
            s["picked_count"] += 1
            s["total_score"] += float(pick.get("predicted_score", 0))
            s["total_predicted_change"] += float(pick.get("predicted_change", 0))

            if pick.get("hit") is True:
                s["wins"] += 1
            elif pick.get("hit") is False:
                s["losses"] += 1
            else:
                s["no_data"] += 1

            actual = pick.get("actual_change")
            if actual is not None:
                s["total_actual_change"] += float(actual)
                s["actual_count"] += 1

            if date > s["last_picked"]:
                s["last_picked"] = date
            if date < s["first_picked"]:
                s["first_picked"] = date

            s["picks"].append({
                "date": date,
                "strategy": strategy,
                "predicted_change": pick.get("predicted_change"),
                "actual_change": pick.get("actual_change"),
                "hit": pick.get("hit"),
                "score": pick.get("predicted_score"),
            })

    # 计算聚合指标
    result = []
    for s in stock_map.values():
        verified = s["wins"] + s["losses"]
        s["win_rate"] = round(s["wins"] / verified * 100, 1) if verified > 0 else None
        s["avg_score"] = round(s["total_score"] / s["picked_count"], 1) if s["picked_count"] > 0 else 0
        s["avg_predicted_change"] = round(s["total_predicted_change"] / s["picked_count"], 2) if s["picked_count"] > 0 else 0
        s["avg_actual_change"] = round(s["total_actual_change"] / s["actual_count"], 2) if s["actual_count"] > 0 else None
        s["strategies"] = list(set(p["strategy"] for p in s["picks"]))
        # 明细按日期倒序
        s["picks"].sort(key=lambda x: x["date"], reverse=True)
        result.append(s)

    # 按选中次数降序 ➜ 胜率降序
    result.sort(key=lambda x: (-x["picked_count"], -(x["win_rate"] or 0)))
    return result


def print_review(strategy: str = None):
    """打印复盘报告"""
    stats = get_stats(strategy)

    print()
    print("=" * 55)
    print(f"   选股复盘报告")
    print("=" * 55)
    print(f"  📅 总天数:     {stats['total_sessions']}")
    print(f"   总推荐:     {stats['total_picks']} 只")
    print(f"  🎯 命中次数:   {stats['hits']}")
    print(f"   综合胜率:   {stats['hit_rate']}%")
    print(f"  💰 平均涨幅:   {stats['avg_actual_change']:+.2f}%")
    print(f"  🧩 策略:       {', '.join(stats['strategies'])}")
    print("=" * 55)

    return stats


# ============ CLI ============

def main():
    """命令行入口"""
    import argparse
    parser = argparse.ArgumentParser(description="选股复盘")
    parser.add_argument("action", nargs="?", default="stats",
                        choices=["stats", "update", "record"])
    parser.add_argument("--date", "-d", help="日期 (YYYY-MM-DD)")
    parser.add_argument("--strategy", "-s", default=None, help="策略筛选")
    args = parser.parse_args()

    if args.action == "stats":
        print_review(args.strategy)
    elif args.action == "update":
        fetch_and_update_actuals(args.date)
    elif args.action == "record":
        print("请使用 API: record_picks(picks, strategy, date)")


if __name__ == "__main__":
    main()
