#!/usr/bin/env python3
"""stock — 统一命令行入口

将全部功能整合到一条命令下：

  stock                     → 运行 basic 选股
  stock basic               → 运行 basic 选股
  stock v2                  → 运行 v2 选股
  stock v3                  → 运行 v3 选股
  stock report              → 生成 HTML 可视化报告
  stock backtest            → 运行策略回测对比
  stock review              → 查看复盘统计
  stock review --update     → 更新昨日复盘数据
  stock pipeline --push     → 运行并推送 Webhook
  stock cache clear         → 清空缓存
  stock --help              → 查看帮助
"""
import sys
import argparse
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(
        prog="stock",
        description=" Stock Analyzer — 股票量化分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  stock                    运行 basic 选股
  stock v3                 运行 v3 多因子选股
  stock report             生成 HTML 报告
  stock backtest           策略回测对比
  stock review             查看复盘统计
  stock pipeline --push    运行并推送到手机
        """,
    )

    parser.add_argument(
        "command", nargs="?", default="basic",
        help="子命令: basic|v2|v3|report|backtest|review|pipeline|cache",
    )
    parser.add_argument("--push", "-p", action="store_true",
                        help="推送结果到 Webhook")
    parser.add_argument("--update", "-u", action="store_true",
                        help="更新复盘数据")
    parser.add_argument("--clear", action="store_true",
                        help="清空缓存")
    parser.add_argument("--output", "-o", default=None,
                        help="报告输出路径 (report 命令)")

    args, extra = parser.parse_known_args()
    cmd = args.command

    # ============ 选股运行 ============
    if cmd in ("basic", "v2", "v3"):
        _run_pipeline(cmd, args.push)

    # ============ 报告 ============
    elif cmd == "report":
        _run_report(args.output)

    # ============ 回测 ============
    elif cmd == "backtest":
        _run_backtest()

    # ============ 复盘 ============
    elif cmd == "review":
        _run_review(args.update)

    # ============ Pipeline ============
    elif cmd == "pipeline":
        mode = extra[0] if extra else "basic"
        _run_pipeline(mode, push=True)

    # ============ 缓存管理 ============
    elif cmd == "cache":
        if args.clear:
            from .cache import clear_all, get_cache_stats
            clear_all()
            print("🗑  Cache cleared")
        else:
            from .cache import get_cache_stats
            stats = get_cache_stats()
            print(f"📦 Cache: {stats['total_keys']} keys, "
                  f"{stats['expired_keys']} expired")

    else:
        parser.print_help()
        sys.exit(1)


# ============ 子命令实现 ============

def _run_pipeline(mode: str, push: bool = False):
    """运行选股流水线"""
    from .main import MODES
    from .review import record_picks

    t0 = datetime.now()
    print(f"🚀 Stock Analyzer — {mode.upper()} — {t0:%Y-%m-%d %H:%M}")

    if mode in MODES:
        picks = MODES[mode]()
        elapsed = (datetime.now() - t0).total_seconds()

        # 自动记录复盘
        record_picks(picks, mode)

        print(f"\n⏱  Done in {elapsed:.1f}s")

        # 自动生成报告
        from .report import generate_report
        generate_report()

        # 推送
        if push:
            from .automation import send_webhook
            result = {
                "success": True,
                "elapsed": elapsed,
                "mode": mode,
                "date": t0.strftime("%Y-%m-%d"),
            }
            try:
                import json, os
                from .config import RESULT_JSON
                if os.path.exists(RESULT_JSON):
                    with open(RESULT_JSON) as f:
                        result["picks"] = json.load(f)
            except Exception:
                pass
            send_webhook(result)
    else:
        print(f" Unknown mode: {mode}")


def _run_report(output: str = None):
    """生成 HTML 可视化报告"""
    from .report import generate_report
    path = generate_report(output_name=output)
    print(f"\n 报告已生成: {path}")
    print(f"   用浏览器打开即可查看")


def _run_backtest():
    """运行策略回测"""
    from .data.loader import load_sw_classification
    from .data.fetcher import fetch_quotes
    from .config import SW_XLS
    from .backtest import run_backtest

    print(" Loading data for backtest...")
    stock = load_sw_classification(SW_XLS)
    quotes = fetch_quotes(stock["tc"].unique().tolist())
    stock = stock.merge(quotes, on="tc", how="inner")
    run_backtest(stock)


def _run_review(update: bool = False):
    """复盘统计"""
    from .review import print_review, fetch_and_update_actuals

    if update:
        print("📡 Fetching actual performance...")
        updated = fetch_and_update_actuals()
        if updated:
            print(f" Updated {updated} records")

    print_review()


if __name__ == "__main__":
    main()
