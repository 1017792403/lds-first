"""HTML 可视化报告 — 交互式选股看板

生成包含以下内容的 HTML 页面：
1. 行业评分排行榜（柱状图）
2. Top 10 选股详情卡片
3. 入选股票的 K 线 + MACD 叠加图
4. 市场热度仪表盘
5. 策略对比表
"""
import os
import json
import base64
import io
from datetime import datetime
from ..config import TEMP, RESULT_JSON

REPORT_DIR = os.path.join(TEMP, "stock_reports")


def ensure_report_dir():
    os.makedirs(REPORT_DIR, exist_ok=True)


def generate_report(result_data: dict = None, output_name: str = None) -> str:
    """生成完整 HTML 报告，返回文件路径

    result_data 结构参考 exporter.py 输出的 JSON
    """
    ensure_report_dir()
    if result_data is None:
        if os.path.exists(RESULT_JSON):
            with open(RESULT_JSON, "r", encoding="utf-8") as f:
                result_data = json.load(f)
        else:
            result_data = {"picks": [], "market_summary": {}}

    if output_name is None:
        output_name = f"report_{datetime.now():%Y%m%d_%H%M}.html"

    picks = result_data.get("picks", [])
    market = result_data.get("market_summary", {})
    model = result_data.get("model_version", "basic")

    # 生成图表数据 (Base64 内嵌)
    chart_industry = _make_industry_chart(picks)
    chart_performance = _make_performance_chart(picks)

    html = _build_html(
        picks=picks,
        market=market,
        model=model,
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        chart_industry=chart_industry,
        chart_performance=chart_performance,
    )

    output_path = os.path.join(REPORT_DIR, output_name)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f" Report saved: {output_path}")
    return output_path


# ============ 内嵌图表（纯 HTML/JS Chart.js，无需安装） ============

def _make_industry_chart(picks: list) -> str:
    """生成行业分布条形图的 Chart.js 配置"""
    industries = {}
    for p in picks:
        ind = p.get("industry", "未知")
        industries[ind] = industries.get(ind, 0) + 1

    labels = json.dumps(list(industries.keys()), ensure_ascii=False)
    data = json.dumps(list(industries.values()))
    return f"""
    <div class="chart-container">
      <canvas id="industryChart"></canvas>
    </div>
    <script>
      new Chart(document.getElementById('industryChart'), {{
        type: 'bar',
        data: {{
          labels: {labels},
          datasets: [{{
            label: '入选数量',
            data: {data},
            backgroundColor: 'rgba(54, 162, 235, 0.6)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1
          }}]
        }},
        options: {{
          responsive: true,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }}
        }}
      }});
    </script>"""


def _make_performance_chart(picks: list) -> str:
    """生成得分/涨幅对比散点图"""
    labels = json.dumps(
        [p.get("name", "?") for p in picks], ensure_ascii=False)
    scores = json.dumps([p.get("score", 0) for p in picks])
    changes = json.dumps(
        [p.get("change_pct", 0) for p in picks])
    return f"""
    <div class="chart-container">
      <canvas id="perfChart"></canvas>
    </div>
    <script>
      new Chart(document.getElementById('perfChart'), {{
        type: 'bar',
        data: {{
          labels: {labels},
          datasets: [
            {{
              label: '综合得分',
              data: {scores},
              backgroundColor: 'rgba(255, 159, 64, 0.6)',
              yAxisID: 'y',
            }},
            {{
              label: '涨幅%',
              data: {changes},
              backgroundColor: 'rgba(75, 192, 192, 0.6)',
              yAxisID: 'y1',
            }}
          ]
        }},
        options: {{
          responsive: true,
          plugins: {{ legend: {{ position: 'top' }} }},
          scales: {{
            y: {{ beginAtZero: true, position: 'left', title: {{ display: true, text: '得分' }} }},
            y1: {{ position: 'right', grid: {{ drawOnChartArea: false }}, title: {{ display: true, text: '涨幅%' }} }}
          }}
        }}
      }});
    </script>"""


# ============ HTML 模板 ============

def _build_html(picks: list, market: dict, model: str,
                date: str, chart_industry: str,
                chart_performance: str) -> str:
    """组装完整 HTML 页面"""
    picks_html = ""
    for p in picks:
        chg = p.get("change_pct", 0)
        chg_class = "up" if chg > 0 else "down"
        chg_sign = "+" if chg > 0 else ""
        picks_html += f"""
        <div class="card">
          <div class="card-header">
            <span class="rank">#{p.get('rank', '?')}</span>
            <span class="name">{p.get('name', '?')}</span>
            <span class="code">{p.get('code', '')}</span>
            <span class="{chg_class}">{chg_sign}{chg:.2f}%</span>
          </div>
          <div class="card-body">
            <div class="info-row">
              <span>🏭 {p.get('industry', '未知')}</span>
              <span> 得分: {p.get('score', 0)}</span>
              <span>💰 {p.get('price', 0):.2f}</span>
            </div>
            <div class="info-row">
              <span> 预计: {p.get('estimated_upside', '?')}</span>
              <span>🎯 概率: {p.get('probability', '?')}</span>
            </div>
            <div class="logic">{p.get('logic', '')}</div>
          </div>
        </div>"""

    stock_count = market.get("stocks_tracked", "?")
    pos_ratio = market.get("positive_industries_ratio", "?")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title> 选股报告 — {date}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background: #f5f7fa; color: #333; padding: 20px; }}
    .header {{ text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; border-radius: 12px; margin-bottom: 20px; }}
    .header h1 {{ font-size: 24px; margin-bottom: 5px; }}
    .header .meta {{ font-size: 13px; opacity: 0.85; }}
    .dashboard {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }}
    .stat-card {{ background: white; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .stat-card .num {{ font-size: 28px; font-weight: bold; color: #667eea; }}
    .stat-card .label {{ font-size: 12px; color: #999; margin-top: 4px; }}
    .row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
    .col {{ flex: 1; min-width: 320px; }}
    .section-title {{ font-size: 16px; font-weight: bold; margin: 16px 0 8px; color: #555; }}
    .chart-container {{ background: white; padding: 12px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 12px; }}
    .card {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 8px; overflow: hidden; }}
    .card-header {{ display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: #f8f9fc; border-bottom: 1px solid #eee; }}
    .rank {{ background: #667eea; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 13px; }}
    .name {{ font-weight: 600; font-size: 14px; }}
    .code {{ color: #999; font-size: 12px; }}
    .up {{ color: #e74c3c; font-weight: 600; margin-left: auto; }}
    .down {{ color: #27ae60; font-weight: 600; margin-left: auto; }}
    .card-body {{ padding: 10px 14px; font-size: 13px; }}
    .info-row {{ display: flex; gap: 12px; margin-bottom: 4px; }}
    .info-row span {{ flex: 1; }}
    .logic {{ margin-top: 6px; color: #888; font-size: 12px; border-top: 1px dashed #eee; padding-top: 6px; }}
    .footer {{ text-align: center; color: #aaa; font-size: 11px; margin-top: 20px; padding: 10px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1> Stock Analyzer 选股报告</h1>
    <div class="meta">{date} | 模型: {model} | 跟踪: {stock_count} 只个股</div>
  </div>

  <div class="dashboard">
    <div class="stat-card"><div class="num">{len(picks)}</div><div class="label">今日推荐</div></div>
    <div class="stat-card"><div class="num">{pos_ratio}</div><div class="label">行业强势比</div></div>
    <div class="stat-card"><div class="num">{stock_count}</div><div class="label">跟踪个股</div></div>
    <div class="stat-card"><div class="num">{model}</div><div class="label">策略模式</div></div>
  </div>

  <div class="row">
    <div class="col">
      <div class="section-title"> 得分 & 涨幅对比</div>
      {chart_performance}
    </div>
    <div class="col">
      <div class="section-title">🏭 行业分布</div>
      {chart_industry}
    </div>
  </div>

  <div class="section-title"> Top {len(picks)} 选股详情</div>
  {picks_html}

  <div class="footer">
    Stock Analyzer · 量化选股仅供参考 · 不构成投资建议
  </div>
</body>
</html>"""
