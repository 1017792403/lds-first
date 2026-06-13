#!/usr/bin/env python3
"""GitHub Actions 运行脚本 — 依次跑三种策略并保存结果"""
import os
import sys
import json
import time
from datetime import datetime

# 设置 TEMP 环境变量（GitHub Actions 没有 TEMP）
if 'TEMP' not in os.environ:
    os.environ['TEMP'] = os.path.join(os.getcwd(), '.temp')
os.makedirs(os.environ['TEMP'], exist_ok=True)
os.makedirs(os.path.join(os.environ['TEMP'], 'stock_reports'), exist_ok=True)

# 确保能找到 stock_analyzer 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 抑制 print
import builtins
_old_print = builtins.print
builtins.print = lambda *a, **k: None

from stock_analyzer.main import MODES
from stock_analyzer.review import record_picks
from stock_analyzer.report import generate_report

results = {}
for mode in ['basic', 'v2', 'v3']:
    print(f"\n[{datetime.now():%H:%M}] Running {mode}...", file=sys.__stdout__)
    try:
        picks = MODES[mode]()
        results[mode] = len(picks)
        record_picks(picks, mode)
        print(f"  {mode}: {len(picks)} picks", file=sys.__stdout__)
    except Exception as e:
        results[mode] = f"ERROR: {e}"
        print(f"  {mode} failed: {e}", file=sys.__stdout__)

builtins.print = _old_print

print(f"\n[{datetime.now():%H:%M}] All done: {json.dumps(results)}", file=sys.__stdout__)
