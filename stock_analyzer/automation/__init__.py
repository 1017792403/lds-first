"""Pipeline 自动化 — 一键调度 + 结果推送

支持：
- 单次运行：python -m stock_analyzer.automation.pipeline basic
- 定时调度：配合 Windows Task Scheduler 使用
- Webhook 推送：企业微信/飞书/DingTalk
"""
import sys
import os
import json
import subprocess
import time
from datetime import datetime
from ..config import TEMP, RESULT_JSON


# ============ 推送通道配置 ============
# 在这里填入你的 Webhook URL
# 支持：企业微信机器人 / 飞书机器人 / DingTalk 机器人
WEBHOOK_URL = os.environ.get("STOCK_WEBHOOK_URL", "")
WEBHOOK_TYPE = os.environ.get("STOCK_WEBHOOK_TYPE", "wechat")  # wechat | feishu | dingtalk


def run_pipeline(mode: str = "basic") -> dict:
    """运行选股流水线，返回结果"""
    print(f"🚀 Stock Pipeline — {mode.upper()} — {datetime.now():%Y-%m-%d %H:%M}")
    t0 = time.time()

    cmd = f'python -m stock_analyzer.main {mode}'
    # Capture output but also let it print
    result = subprocess.run(cmd, shell=True, capture_output=False, text=True)
    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f" Pipeline failed after {elapsed:.1f}s")
        return {"success": False, "elapsed": elapsed}

    # 读取结果
    picks = []
    if os.path.exists(RESULT_JSON):
        with open(RESULT_JSON, "r", encoding="utf-8") as f:
            picks = json.load(f)

    print(f" Pipeline done in {elapsed:.1f}s")
    return {
        "success": True,
        "elapsed": elapsed,
        "mode": mode,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "picks": picks,
    }


# ============ Webhook 推送 ============

def build_wechat_message(result: dict) -> dict:
    """构建企业微信机器人消息"""
    picks = result.get("picks", {}).get("picks", [])
    if not picks:
        return {"msgtype": "text", "text": {"content": " 今日选股结果为空"}}

    lines = [f" 选股结果 | {result['date']} | {result['mode']}"]
    lines.append("━" * 20)
    for p in picks[:5]:
        lines.append(
            f"#{p['rank']} {p['name']}({p['code']}) "
            f"{p.get('industry', '')} "
            f"得分{p['score']} | {p.get('change_pct', 0):+.1f}%"
        )
    lines.append("━" * 20)
    lines.append(f"模式: {result['mode']} | 耗时: {result['elapsed']:.1f}s")

    return {"msgtype": "text", "text": {"content": "\n".join(lines)}}


def build_feishu_message(result: dict) -> dict:
    """构建飞书机器人消息"""
    picks = result.get("picks", {}).get("picks", [])
    if not picks:
        return {"msg_type": "text", "content": {"text": "今日选股结果为空"}}

    content = f" 选股结果 | {result['date']}\n"
    content += "━" * 20 + "\n"
    for p in picks[:5]:
        content += (
            f"#{p['rank']} {p['name']}({p['code']})\n"
            f"  板块:{p.get('industry', '')} "
            f"得分:{p['score']} "
            f"涨幅:{p.get('change_pct', 0):+.1f}%\n"
        )
    content += f"\n模式: {result['mode']} | 耗时: {result['elapsed']:.1f}s"

    return {"msg_type": "text", "content": {"text": content}}


def build_dingtalk_message(result: dict) -> dict:
    """构建钉钉机器人消息"""
    picks = result.get("picks", {}).get("picks", [])
    if not picks:
        return {"msgtype": "text", "text": {"content": "今日选股结果为空"}}
    texts = [f" 选股结果 {result['date']}"]
    for p in picks[:5]:
        texts.append(f"{p['rank']}.{p['name']}({p['code']}) {p.get('change_pct', 0):+.1f}%")
    return {"msgtype": "text", "text": {"content": "\n".join(texts)}}


def send_webhook(result: dict, webhook_url: str = WEBHOOK_URL,
                 webhook_type: str = WEBHOOK_TYPE):
    """发送 Webhook 推送"""
    if not webhook_url:
        print("  未配置 WEBHOOK_URL，跳过推送")
        print("   设置环境变量 STOCK_WEBHOOK_URL 或修改 automation/__init__.py")
        return False

    builders = {
        "wechat": build_wechat_message,
        "feishu": build_feishu_message,
        "dingtalk": build_dingtalk_message,
    }
    builder = builders.get(webhook_type, build_wechat_message)
    payload = builder(result)

    import urllib.request
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        print(f" Webhook sent ({webhook_type})")
        return True
    except Exception as e:
        print(f" Webhook failed: {e}")
        return False


# ============ CLI ============

def main():
    """命令行入口：python -m stock_analyzer.automation.pipeline [mode] [--push]"""
    import argparse

    parser = argparse.ArgumentParser(description="Stock Pipeline Automation")
    parser.add_argument("mode", nargs="?", default="basic",
                        choices=["basic", "v2", "v3"],
                        help="选股模式 (default: basic)")
    parser.add_argument("--push", "-p", action="store_true",
                        help="运行后推送结果到 Webhook")
    parser.add_argument("--schedule", action="store_true",
                        help="生成 Windows 定时任务配置说明")

    args = parser.parse_args()

    if args.schedule:
        print_schedule_guide()
        return

    result = run_pipeline(args.mode)

    if args.push and result["success"]:
        send_webhook(result)


def print_schedule_guide():
    """打印定时任务配置说明"""
    script_path = os.path.abspath(__file__)
    print("=" * 60)
    print("  Windows 定时任务配置指南")
    print("=" * 60)
    print()
    print("  1. 打开「任务计划程序」")
    print("  2. 创建基本任务 → 名称: StockDaily")
    print("  3. 触发器: 每天 08:30")
    print("  4. 操作: 启动程序")
    print(f"  5. 程序或脚本: python")
    print(f"  6. 参数: -m stock_analyzer.automation.pipeline basic --push")
    print(f"  7. 起始于: {os.path.dirname(script_path)}")
    print()
    print("  或直接运行以下命令创建（需要管理员权限）：")
    print()
    print(f"    schtasks /create /tn StockDaily /tr "
          f"\"python -m stock_analyzer.automation.pipeline basic --push\" "
          f"/sc daily /st 08:30 /f")
    print()


if __name__ == "__main__":
    main()
