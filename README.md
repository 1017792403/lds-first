# Project_01: 股票分析工具优化

## 模块化重构

将 12 个零散脚本（pipeline.py → v9_clean.py）重构为规范的 Python 包。

## 项目结构

```
stock_analyzer/
├── __init__.py              # 包声明
├── config.py                # 全局配置（路径、参数、事件板块定义）
├── main.py                  # 主入口（支持 3 种策略模式）
├── data/
│   ├── loader.py            # 加载申万行业分类 + 行业名称
│   ├── fetcher.py           # 腾讯行情 API 批量拉取
│   └── kline.py             # K线数据获取
├── analysis/
│   ├── indicators.py        # 技术指标（MACD, KDJ, 量比, 斜率, 背离）
│   ├── scorer.py            # 行业/个股评分引擎（basic + v2）
│   └── screener.py          # 候选池构建
└── output/
    ├── reporter.py          # 控制台格式化输出
    └── exporter.py          # JSON 结果导出
```

## 策略模式

| 模式 | 说明 | 对应原脚本 |
|------|------|-----------|
| `basic` | 经典行业+个股评分 | pipeline.py, stock_picker.py |
| `v2` | 过热修正+缩量惩罚+板块加成 | pipeline_v2.py |
| `v3` | 事件+技术+人性 三因子 | pipeline_v3.py, pipeline_v3_final.py |

## 使用

```bash
# 安装依赖
pip install pandas numpy akshare

# 运行（basic 为默认）
python -m stock_analyzer.main basic
python -m stock_analyzer.main v2
python -m stock_analyzer.main v3
```

## 相比原脚本的改进

- ✅ 消除 90%+ 重复代码
- ✅ 模块职责清晰，单文件不超过 300 行
- ✅ 统一配置管理，参数调整无需改代码
- ✅ 可扩展策略接口，新增模式只需加函数
- ✅ 进度回调，运行过程可视化
