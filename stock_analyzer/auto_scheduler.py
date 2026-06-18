"""自动调度器 — 每天 08:00 / 17:00 自动运行三种策略并记录

嵌入到 Flask 服务器中，服务器启动后自动在后台运行。
"""
import os
import sys
import json
import time
import threading
import builtins as _builtins
from datetime import datetime, timedelta


# 调度时间（24 小时制）
SCHEDULE_HOURS = [8, 17]  # 早上 8 点和下午 5 点

# 记录已运行的时段，防止同一天重复执行
_ran_today = set()  # e.g. {"2026-06-13_8", "2026-06-13_17"}


def _get_today_key(hour: int) -> str:
    """生成唯一键防止重复运行：'2026-06-13_8'"""
    return f"{datetime.now():%Y-%m-%d}_{hour}"


def run_all_strategies():
    """运行三种策略并记录结果"""
    from stock_analyzer.main import MODES
    from stock_analyzer.review import record_picks, fetch_and_update_actuals

    # 抑制 print 输出
    _old_print = _builtins.print
    _builtins.print = lambda *a, **k: None

    results = {}
    try:
        for mode in ['basic', 'v2', 'v3']:
            try:
                picks = MODES[mode]()
                results[mode] = len(picks)
                record_picks(picks, mode)
            except Exception as e:
                results[mode] = f"error: {e}"
    finally:
        _builtins.print = _old_print

    # 验证前一日选股的实际涨跌幅
    try:
        fetch_and_update_actuals()
    except Exception:
        pass

    return results


def scheduler_loop():
    """调度器主循环（每分钟检查一次）"""
    while True:
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        if hour in SCHEDULE_HOURS and minute == 0:
            # 非交易日跳过（周末）
            if now.weekday() >= 5:
                time.sleep(61)
                continue

            today_key = _get_today_key(hour)
            if today_key not in _ran_today:
                _ran_today.add(today_key)
                print(f"\n[Auto Scheduler] Running at {now:%Y-%m-%d %H:%M}...")
                try:
                    result = run_all_strategies()
                    print(f"[Auto Scheduler] Done: {result}")
                except Exception as e:
                    print(f"[Auto Scheduler] Error: {e}")

            # 睡 61 秒避免同一分钟重复触发
            time.sleep(61)
        else:
            time.sleep(30)


def _load_review_dates() -> list:
    """从 data/review_history.json 读取已有的日期列表"""
    paths = [
        os.path.join(os.getcwd(), "data", "review_history.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "review_history.json"),
    ]
    for p in paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                records = json.load(f)
            return sorted(set(r["date"] for r in records))
    return []


def _catchup_missing_days():
    """启动时检查是否有缺失的交易日，补录选股"""
    from stock_analyzer.main import MODES
    from stock_analyzer.review import record_picks

    existing = _load_review_dates()
    if not existing:
        return

    today = datetime.now().strftime("%Y%m%d")
    last = existing[-1]

    # 只补最近 3 个工作日的缺失
    missing = [d for d in _get_recent_trading_days(today, 5) if d not in existing and d > last]
    if not missing:
        return

    # 只补一天前的（太早的用 backfill 脚本单独跑更准）
    for d in missing:
        print(f"[Auto Scheduler] Catch-up: running strategies for {d}")

    _old_print = _builtins.print
    _builtins.print = lambda *a, **k: None
    for mode in ['basic', 'v2', 'v3']:
        try:
            picks = MODES[mode]()
            if picks:
                record_picks(picks, mode)
        except Exception:
            pass
    _builtins.print = _old_print
    print(f"[Auto Scheduler] Catch-up done: strategies run for missing days")


def _get_recent_trading_days(today: str, count: int) -> list:
    """返回最近 N 个可能的交易日（粗略，跳过周末）"""
    from datetime import datetime, timedelta
    dt = datetime.strptime(today, "%Y%m%d")
    days = []
    while len(days) < count:
        if dt.weekday() < 5:  # 周一到周五
            days.append(dt.strftime("%Y%m%d"))
        dt -= timedelta(days=1)
    return sorted(days)


def start():
    """启动调度器（在后台线程中运行）"""
    # 启动时补录缺失天数
    try:
        _catchup_missing_days()
    except Exception:
        pass

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    print(f"[Auto Scheduler] Started: daily runs at {SCHEDULE_HOURS}:00")
