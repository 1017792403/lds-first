#!/usr/bin/env python3
"""Stock Analyzer — Web App

双击桌面图标启动，浏览器打开即可点击使用。
"""
import os
import sys
import json
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request

# 强制 UTF-8 输出，避免 GBK 终端打印 emoji 崩溃
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
# 重新配置标准输出
import io
for s_name in ['stdout', 'stderr']:
    s = getattr(sys, s_name)
    if hasattr(s, 'reconfigure'):
        try:
            s.reconfigure(encoding='utf-8')
        except Exception:
            pass
    elif hasattr(s, 'buffer'):
        setattr(sys, s_name, io.TextIOWrapper(s.buffer, encoding='utf-8'))

# 添加项目根目录到 path
_app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

app = Flask(__name__)

# ============ 全局状态 ============
_latest_result = None
_latest_report_path = None


# ============ 页面路由 ============

@app.route("/")
def index():
    """仪表盘主页"""
    return render_template("dashboard.html")


@app.route("/run", methods=["POST"])
def run_analysis():
    """运行选股（点击按钮触发）"""
    global _latest_result, _latest_report_path

    mode = request.json.get("mode", "basic")

    # 临时抑制 print 输出，避免 werkzeug 的 stdout 编码问题
    import builtins
    _old_print = builtins.print
    builtins.print = lambda *a, **k: None

    try:
        from stock_analyzer.main import MODES
        from stock_analyzer.report import generate_report

        t0 = time.time()
        picks = MODES[mode]()
        elapsed = round(time.time() - t0, 1)

        # 恢复 print
        builtins.print = _old_print

        # 生成 HTML 报告
        report_name = f"report_{datetime.now():%Y%m%d_%H%M%S}.html"
        report_path = generate_report(output_name=report_name)
        _latest_report_path = report_path

        # 整理结果
        result = {
            "success": True,
            "mode": mode,
            "elapsed": elapsed,
            "picks_count": len(picks),
            "picks": [],
        }
        for i, p in enumerate(picks):
            # p may be a pandas Series - convert safely
            def _get(key, default=None):
                val = p.get(key, default) if hasattr(p, 'get') else p.get(key, default)
                # Handle numpy/pandas types
                if hasattr(val, 'item'):
                    val = val.item()
                return val

            result["picks"].append({
                "rank": i + 1,
                "name": _get("name", _get("name_y", "?")),
                "code": _get("stock_code", _get("code", "?")),
                "industry": _get("ind_name", _get("industry", "?")),
                "price": float(_get("price", _get("price_x", 0))),
                "change_pct": float(_get("change_pct", _get("chg_pct", _get("chg", 0)))),
                "score": round(float(_get("final_score", _get("final", 0))), 1),
                "logic": _get("logic", ""),
            })

        _latest_result = result
        return jsonify(result)

    except Exception as e:
        # 恢复 print
        builtins.print = _old_print
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/report")
def view_report():
    """查看最新生成的 HTML 报告"""
    if _latest_report_path and os.path.exists(_latest_report_path):
        with open(_latest_report_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h2>暂无报告</h2><p>请先运行选股</p>"


@app.route("/review")
def review_page():
    """复盘页面"""
    return render_template("review.html")


@app.route("/api/review")
def api_review():
    """复盘数据 API"""
    from stock_analyzer.review import get_stats, _load_history
    stats = get_stats()
    history = _load_history()
    return jsonify({"stats": stats, "history": history[-30:]})  # 近30天


@app.route("/backtest")
def backtest_page():
    """回测页面"""
    return render_template("backtest.html")


@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    """运行回测"""
    from stock_analyzer.data.loader import load_sw_classification
    from stock_analyzer.data.fetcher import fetch_quotes
    from stock_analyzer.backtest import run_backtest
    from stock_analyzer.config import SW_XLS

    stock = load_sw_classification(SW_XLS)
    quotes = fetch_quotes(stock["tc"].unique().tolist())
    stock = stock.merge(quotes, on="tc", how="inner")

    result = run_backtest(stock)
    return jsonify({
        "success": True,
        "data": result.to_dict(orient="records"),
    })


@app.route("/cache")
def cache_page():
    """缓存管理页面"""
    from stock_analyzer.cache import get_cache_stats, clear_all
    return render_template("cache.html")


@app.route("/api/cache")
def api_cache():
    """缓存状态 API"""
    from stock_analyzer.cache import get_cache_stats
    return jsonify(get_cache_stats())


@app.route("/api/cache/clear", methods=["POST"])
def api_cache_clear():
    """清空缓存"""
    from stock_analyzer.cache import clear_all
    clear_all()
    return jsonify({"success": True})


# ============ 选股配置 API ============

@app.route("/settings")
def settings_page():
    """选股逻辑设置页面"""
    return render_template("settings.html")


@app.route("/api/config", methods=["GET"])
def api_get_config():
    """获取当前选股配置"""
    from stock_analyzer.config_manager import get_config
    return jsonify(get_config())


@app.route("/api/config", methods=["PUT"])
def api_update_config():
    """更新选股配置"""
    from stock_analyzer.config_manager import update_config, apply_user_config
    updates = request.get_json()
    config = update_config(updates)
    apply_user_config()
    return jsonify({"success": True, "config": config})


@app.route("/api/config/reset", methods=["POST"])
def api_reset_config():
    """重置选股配置为默认"""
    from stock_analyzer.config_manager import reset_config, apply_user_config
    config = reset_config()
    apply_user_config()
    return jsonify({"success": True, "config": config})


# ============ 启动 ============



def main():
    # 启动自动调度器
    try:
        from stock_analyzer.auto_scheduler import start as start_scheduler
        start_scheduler()
    except Exception:
        pass

    # 加载用户自定义配置
    try:
        from stock_analyzer.config_manager import apply_user_config
        apply_user_config()
    except Exception:
        pass

    port = int(os.environ.get("PORT", 8765))
    print()
    print("=" * 46)
    print("  Stock Analyzer Web App")
    print()
    print("  Starting at http://127.0.0.1:{}".format(port))
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 46)
    print()
    # 自动打开浏览器
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
