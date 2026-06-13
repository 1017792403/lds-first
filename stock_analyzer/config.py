"""全局配置 — 路径、常量、事件板块定义"""

import os

# ============ 路径配置 ============
TEMP = os.environ.get("TEMP", ".")
SW_XLS = os.path.join(TEMP, "sw.xls")          # 申万行业分类 Excel
RESULT_JSON = os.path.join(TEMP, "result.json") # 默认输出路径

# ============ 行情 API 参数 ============
QUOTE_BATCH_SIZE = 80        # 每批拉取股票数
QUOTE_TIMEOUT = 15           # 单次请求超时（秒）
QUOTE_INTERVAL = 0.3         # 批次间隔（秒）
QUOTE_URL = "https://qt.gtimg.cn/q={}"

KLINE_URL = "https://ifzq.gtimg.cn/appstock/app/fqkline/get?param={},day,,,{},qfq"
KLINE_DEFAULT_DAYS = 40
KLINE_TIMEOUT = 8
KLINE_INTERVAL = 0.08

# ============ 选股参数 ============
CANDIDATES_PER_INDUSTRY = 15  # 每个行业初选候选数
TOP_N_FINAL = 10               # 最终推荐数
MAX_PER_INDUSTRY = 3           # 单行业最大入选数（v2 用 2）

# ============ 行业评分权重 ============
INDUSTRY_WEIGHTS = {
    "avg_change": 0.30,    # 行业平均涨幅
    "rise_ratio": 0.20,    # 上涨家数占比
    "top3_change": 0.25,   # 前三领涨股均值
    "total_amount": 0.15,  # 总成交额
    "surge_count": 0.10,   # 大涨（>5%）家数
}

# ============ 个股评分权重 ============
STOCK_WEIGHTS = {
    "change_pct": 0.35,    # 涨幅
    "rel_strength": 0.30,  # 板块内相对强度
    "vol_ratio": 0.20,     # 量比
    "amount": 0.15,        # 成交额
}

# 行业得分加成比例
INDUSTRY_BOOST_RATIO = 0.3

# ============ 市场状态阈值 ============
MARKET_THRESHOLDS = {
    "strong": (0.6, 20),    # (positive_ratio, M)
    "neutral": (0.3, 12),
    "weak": (0.0, 6),
}

# ============ 事件驱动板块定义（v3+ 用）============
# { l2_code: (event_score, exposure_score, driver, psychology_note, psych_score) }
EVENT_SECTORS_FULL = {
    "6502": (100, 95, "SpaceX史上最大IPO→商业航天", "FOMO极高(70%)", 35),
    "6505": (85, 85, "商业航天扩散至航空装备", "高FOMO(65%)", 30),
    "2701": (85, 90, "长鑫科技IPO获批+存储龙头扩产", "基本面驱动FOMO适中(60%)", 70),
    "2703": (75, 80, "存储龙头扩产→设备需求增长", "行业景气(55%)", 65),
    "2403": (60, 60, "工业金属商品周期上涨", "机构主导散户温和(45%)", 80),
    "2404": (50, 55, "小金属跟随工业金属", "机构主导(40%)", 75),
    "4901": (40, 80, "沪指放量利好券商", "散户关注(55%)", 55),
    "7104": (35, 65, "AI数字经济金融科技", "科技股情绪(50%)", 60),
    "6307": (35, 50, "商业航天扩散到卫星通信", "中性", 50),
}

# 精简版事件板块（v4 用）
EVENT_SECTORS_LITE = {
    "2701": (80, "长鑫IPO+存储扩产+光刻胶"),
    "6502": (70, "SpaceX上市首日+20%"),
    "6505": (65, "SpaceX热度卫星"),
    "2403": (55, "工业金属周期"),
    "2404": (50, "小金属"),
    "7104": (40, "AI金融科技"),
    "6307": (35, "卫星通信"),
    "4901": (30, "放量利好券商"),
}

# ============ V2 修正因子参数 ============
OVERHEAT_THRESHOLDS = [
    (15, 0.5),    # (chg%, penalty)
    (12, 0.7),
    (8, 0.85),
    (0, 1.0),
]

VOLUME_PENALTY_THRESHOLDS = [
    (1.0, 0.6),
    (1.2, 0.8),
    (float("inf"), 1.0),
]
