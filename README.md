# 股票分析工具 (Stock Analyzer)

A股量化选股工具，支持 3 种选股策略、Web 仪表盘、自动复盘、历史回测。

> **仓库地址：** https://github.com/1017792403/lds-first
> 项目位于仓库中的 `Project_01_股票分析工具优化/` 目录。

---

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/1017792403/lds-first.git
cd lds-first/Project_01_股票分析工具优化

# 2. 安装依赖
pip install flask pandas numpy

# 3. 启动 Web 仪表盘
python -m stock_analyzer.app

# 4. 浏览器打开 http://127.0.0.1:8765
```

---

## 功能一览

| 功能 | 说明 |
|------|------|
| **📊 Web 仪表盘** | 可视化展示当日选股结果、评分、板块分布、选中理由 |
| **📈 复盘系统** | 记录每天每只选股的次日实际涨跌幅，计算策略胜率 |
| **📋 个股历史统计** | 按股票代码聚合，查看每只股票被选中的次数、胜率、平均涨幅 |
| **🔔 自动调度** | 每天 08:00 / 17:00 自动运行三种策略，记录复盘数据 |
| **☁️ GitHub Actions** | 云调度，推送数据到仓库 |
| **📉 回测系统** | 历史数据回测，验证策略有效性 |
| **📰 新闻驱动** | 东方财富热搜 → 行业映射，V3 策略的事件因子 |

---

## 3 种选股策略

| 策略 | 核心逻辑 | 平均胜率 |
|------|---------|---------|
| **Basic** | 行业评分 + 个股评分 | ~52% |
| **V2** | 过热修正 + 缩量惩罚 + 板块加成 | ~49% |
| **V3** | 事件驱动 + 技术面 + 人性三因子 | ~52% |

### 运行单个策略

```bash
python -m stock_analyzer.cli basic   # 经典策略
python -m stock_analyzer.cli v2      # V2 策略
python -m stock_analyzer.cli v3      # V3 策略
```

---

## 项目结构

```
stock_analyzer/
├── app/                    # Flask Web 应用
│   ├── __init__.py         # 路由、API 接口
│   └── templates/          # HTML 模板
│       ├── dashboard.html  # 仪表盘首页
│       ├── review.html     # 复盘页面
│       ├── backtest.html   # 回测页面
│       └── settings.html   # 设置页
├── analysis/               # 选股算法
│   ├── scorer.py           # 行业/个股评分引擎
│   ├── screener.py         # 候选池 + 事件驱动池
│   ├── indicators.py       # 技术指标计算
│   ├── explainer.py        # 选中理由生成
│   └── news_driver.py      # 新闻热点驱动
├── data/                   # 数据获取
│   ├── fetcher.py          # 腾讯行情 API
│   ├── kline.py            # K 线数据
│   └── loader.py           # 申万行业分类
├── review/                 # 复盘系统
│   └── __init__.py         # 记录、统计、验证
├── main.py                 # 策略入口
├── auto_scheduler.py       # 自动调度器
├── config.py               # 全局配置
└── cli.py                  # 命令行入口
```

---

## 复盘系统

每次运行策略后，选股记录自动写入 `data/review_history.json`。次交易日自动回填实际涨跌幅，计算命中率。

```
复盘页面 (/review) 可查看：
┌─────────────────────────────────────────┐
│ 统计卡片：运行天数 / 总推荐 / 已复盘    │
│         综合胜率 / 平均涨幅              │
│ 分策略卡片：Basic V2 V3 各自胜率+涨幅    │
├─────────────────────────────────────────┤
│ 三种策略每日胜率折线图                   │
├─────────────────────────────────────────┤
│ 历史记录表格 — 点击展开当日选股明细      │
├─────────────────────────────────────────┤
│ 个股历史统计 — 搜索股票看历史表现        │
└─────────────────────────────────────────┘
```

---

## 自动调度

### 本地调度（需保持 Flask 运行）
```bash
python -m stock_analyzer.app
# 调度器在后台运行，每天 08:00 / 17:00 自动触发
```

### GitHub Actions 云调度
仓库已配置 `.github/workflows/stock-daily.yml`，每天 UTC 00:00 / 09:00（北京时间 08:00 / 17:00）自动运行，结果推送到仓库。

---

## 常见问题

**Q: 为什么有些股票没有复盘数据？**
A: 当天的选股需要下一个交易日才能验证涨跌幅。周末非交易日也会跳过。

**Q: 数据存在哪里？**
A: 所有复盘数据存储在 `data/review_history.json`，GitHub Actions 运行结果也会自动推送。

**Q: 如何回填历史数据？**
A: 运行 `python scripts/backfill_history.py` 可回填近 30 个交易日的数据。

---

## 依赖

- Python >= 3.11
- flask
- pandas
- numpy
