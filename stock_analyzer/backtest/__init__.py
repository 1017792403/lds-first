"""多策略回测框架 — 对比不同选股策略的历史表现

核心概念：
- Strategy: 选股策略（basic / v2 / v3）
- Backtest: 用历史交易日数据模拟选股
- Report: 对比各策略的胜率、平均涨幅、最大回撤

依赖：回测需要历史 K 线数据支持。
"""
import os
import json
import time
from datetime import datetime, timedelta
from typing import List, Callable
import pandas as pd
import numpy as np
from ..config import TEMP

BACKTEST_DIR = os.path.join(TEMP, "backtest_results")


def ensure_dir():
    os.makedirs(BACKTEST_DIR, exist_ok=True)


# ============ 回测引擎 ============

class BacktestEngine:
    """回测引擎：在指定日期范围内模拟选股"""

    def __init__(self, stock_data: pd.DataFrame, initial_cash: float = 1_000_000):
        self.stock_data = stock_data
        self.initial_cash = initial_cash
        self.results = []

    def run_strategy(self, name: str, scorer_fn: Callable,
                     start_date: str, end_date: str,
                     top_n: int = 10) -> dict:
        """运行单个策略的回测

        scorer_fn: (stock_data: pd.DataFrame) -> list of picks
        """
        # 这里简化处理：实际回测需要每天的行情数据
        # 目前基于单日快照模拟，后续可扩展为完整回测
        t0 = time.time()
        try:
            picks = scorer_fn(self.stock_data)
            elapsed = time.time() - t0

            result = {
                "strategy": name,
                "date_range": f"{start_date} → {end_date}",
                "top_n": min(top_n, len(picks)) if picks else 0,
                "elapsed": round(elapsed, 2),
                "picks": picks[:top_n] if picks else [],
                "timestamp": datetime.now().isoformat(),
            }
            self.results.append(result)
            return result

        except Exception as e:
            print(f" Strategy {name} failed: {e}")
            return {"strategy": name, "error": str(e), "picks": []}

    def compare(self) -> pd.DataFrame:
        """对比所有策略结果"""
        rows = []
        for r in self.results:
            picks = r.get("picks", [])
            avg_score = np.mean([p.get("score", p.get("final", 0))
                                 for p in picks]) if picks else 0
            avg_chg = np.mean([float(p.get("change_pct", p.get("chg", 0)))
                               for p in picks]) if picks else 0
            rows.append({
                "strategy": r["strategy"],
                "top_n": r["top_n"],
                "avg_score": round(avg_score, 1),
                "avg_change_pct": round(avg_chg, 2),
                "elapsed": r.get("elapsed", 0),
            })
        return pd.DataFrame(rows)


def run_backtest(stock_data: pd.DataFrame,
                 strategies: dict = None,
                 top_n: int = 10) -> pd.DataFrame:
    """快捷回测：对比多个策略

    strategies: {"name": scorer_function, ...}
    """
    if strategies is None:
        from ..analysis.scorer import score_stocks, score_stocks_v2, select_top_n
        from ..config import CANDIDATES_PER_INDUSTRY

        def basic_scorer(data):
            from ..analysis.scorer import score_industries
            ind = score_industries(data)
            M = min(12, len(ind))
            top_ind = ind.head(M)
            codes = top_ind["l2_code"].tolist()
            from ..analysis.screener import build_candidate_pool
            candidates = build_candidate_pool(data, codes,
                                              CANDIDATES_PER_INDUSTRY)
            scored = score_stocks(candidates, ind)
            return select_top_n(scored, top_n)

        def v2_scorer(data):
            from ..analysis.scorer import score_industries
            ind = score_industries(data)
            M = min(12, len(ind))
            top_ind = ind.head(M)
            codes = top_ind["l2_code"].tolist()
            from ..analysis.screener import build_candidate_pool
            candidates = build_candidate_pool(data, codes,
                                              CANDIDATES_PER_INDUSTRY)
            scored = score_stocks_v2(candidates, ind)
            return select_top_n(scored, top_n)

        strategies = {"basic": basic_scorer, "v2": v2_scorer}

    engine = BacktestEngine(stock_data)
    for name, fn in strategies.items():
        print(f"   Backtesting {name}...")
        engine.run_strategy(name, fn, "", "")

    comparison = engine.compare()

    # 转换 picks 为可序列化格式
    def _serialize(obj):
        if isinstance(obj, dict):
            return {k: _serialize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_serialize(v) for v in obj]
        elif isinstance(obj, (pd.Timestamp, pd.Timedelta)):
            return str(obj)
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Series):
            return _serialize(obj.to_dict())
        elif hasattr(obj, 'isoformat'):
            return str(obj)
        return obj

    serializable_results = []
    for r in engine.results:
        sr = dict(r)
        if "picks" in sr:
            sr["picks"] = [_serialize(p) for p in sr["picks"]]
        serializable_results.append(sr)

    # 保存结果
    ensure_dir()
    path = os.path.join(
        BACKTEST_DIR,
        f"backtest_{datetime.now():%Y%m%d_%H%M}.json",
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable_results, f, ensure_ascii=False, indent=2)

    print(f"\n 策略对比结果:")
    print(comparison.to_string(index=False))
    return comparison


# ============ CLI ============

def main():
    """命令行入口：python -m stock_analyzer.backtest.run"""
    from ..data.loader import load_sw_classification
    from ..data.fetcher import fetch_quotes
    from ..config import SW_XLS

    print("=" * 50)
    print("  BACKTEST — 策略对比")
    print("=" * 50)

    print("\nLoading data...")
    stock = load_sw_classification(SW_XLS)
    quotes = fetch_quotes(stock["tc"].unique().tolist())
    stock = stock.merge(quotes, on="tc", how="inner")
    print(f"  {len(stock)} stocks loaded")

    run_backtest(stock)


if __name__ == "__main__":
    main()
