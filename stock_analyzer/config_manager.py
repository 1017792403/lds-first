"""配置管理器 — 运行时读写选股参数

用户在前端修改的选股逻辑参数保存到 user_config.json，
运行时覆盖 stock_analyzer/config.py 的默认值。
"""
import os
import json
from copy import deepcopy
from .config import (
    TEMP, INDUSTRY_WEIGHTS, STOCK_WEIGHTS, MARKET_THRESHOLDS,
    CANDIDATES_PER_INDUSTRY, MAX_PER_INDUSTRY, TOP_N_FINAL,
    INDUSTRY_BOOST_RATIO, OVERHEAT_THRESHOLDS, VOLUME_PENALTY_THRESHOLDS,
    EVENT_SECTORS_FULL,
)

USER_CONFIG_PATH = os.path.join(TEMP, "user_config.json")


# ============ 默认配置（供前端展示） ============

DEFAULT_CONFIG = {
    "industry_weights": {
        "avg_change": {"value": 0.30, "label": "行业平均涨幅", "desc": "板块整体涨跌对行业评分的影响权重"},
        "rise_ratio": {"value": 0.20, "label": "上涨家数占比", "desc": "板块内上涨股票比例的权重"},
        "top3_change": {"value": 0.25, "label": "前三领涨股均值", "desc": "板块龙头强度的权重"},
        "total_amount": {"value": 0.15, "label": "总成交额", "desc": "资金关注度的权重"},
        "surge_count": {"value": 0.10, "label": "大涨(>5%)家数", "desc": "板块赚钱效应深度的权重"},
    },
    "stock_weights": {
        "change_pct": {"value": 0.35, "label": "当日涨幅", "desc": "个股价格强度权重"},
        "rel_strength": {"value": 0.30, "label": "板块内相对强度", "desc": "个股在板块中是否领涨"},
        "vol_ratio": {"value": 0.20, "label": "量比", "desc": "成交量是否放大的权重"},
        "amount": {"value": 0.15, "label": "成交额", "desc": "资金介入深度的权重"},
    },
    "selection_params": {
        "top_n": {"value": 10, "label": "最终推荐数", "desc": "最终输出的股票数量"},
        "max_per_industry": {"value": 3, "label": "单行业最大入选数", "desc": "同一行业最多入选几只"},
        "candidates_per_industry": {"value": 15, "label": "每行业初选候选数", "desc": "每个行业取成交额前N名"},
        "industry_boost_ratio": {"value": 0.30, "label": "行业得分加成比例", "desc": "个股最终得分中行业分的占比"},
    },
    "market_thresholds": {
        "strong": {
            "label": "牛市",
            "positive_ratio_min": 0.60,
            "industry_count": 20,
            "desc": "上涨行业占比 > 60% 时视为牛市，选前 M 个行业"
        },
        "neutral": {
            "label": "震荡市",
            "positive_ratio_min": 0.30,
            "industry_count": 12,
            "desc": "上涨行业占比 30-60% 时视为震荡市"
        },
        "weak": {
            "label": "熊市",
            "positive_ratio_min": 0.00,
            "industry_count": 6,
            "desc": "上涨行业占比 < 30% 时视为熊市"
        },
    },
    "v2_correction": {
        "overheat_thresholds": {
            "label": "过热惩罚阈值",
            "desc": "涨幅超过阈值时降低权重",
            "rules": [
                {"max_chg": 15, "penalty": 0.50, "label": "涨幅 > 15%"},
                {"max_chg": 12, "penalty": 0.70, "label": "涨幅 > 12%"},
                {"max_chg": 8, "penalty": 0.85, "label": "涨幅 > 8%"},
                {"max_chg": 0, "penalty": 1.00, "label": "其他"},
            ],
        },
        "volume_penalty": {
            "label": "缩量惩罚阈值",
            "desc": "量比不足时降低权重",
            "rules": [
                {"max_ratio": 1.0, "penalty": 0.60, "label": "量比 < 1.0"},
                {"max_ratio": 1.2, "penalty": 0.80, "label": "量比 < 1.2"},
                {"max_ratio": 999, "penalty": 1.00, "label": "其他"},
            ],
        },
    },
    "v3_event_sectors": {
        "label": "事件驱动板块 (V3)",
        "desc": "V3 策略使用的事件板块评分",
        "sectors": [
            {"code": "6502", "name": "航天装备Ⅱ", "event_score": 100, "exposure": 95, "driver": "SpaceX史上最大IPO→商业航天"},
            {"code": "6505", "name": "军工电子Ⅱ", "event_score": 85, "exposure": 85, "driver": "商业航天扩散至航空装备"},
            {"code": "2701", "name": "半导体", "event_score": 85, "exposure": 90, "driver": "长鑫科技IPO获批+存储龙头扩产"},
            {"code": "2403", "name": "工业金属", "event_score": 60, "exposure": 60, "driver": "工业金属商品周期上涨"},
            {"code": "2404", "name": "贵金属", "event_score": 50, "exposure": 55, "driver": "小金属跟随工业金属"},
            {"code": "4901", "name": "证券Ⅱ", "event_score": 40, "exposure": 80, "driver": "沪指放量利好券商"},
            {"code": "7104", "name": "软件开发", "event_score": 35, "exposure": 65, "driver": "AI数字经济金融科技"},
            {"code": "6307", "name": "电池", "event_score": 35, "exposure": 50, "driver": "商业航天扩散到卫星通信"},
        ],
    },
}


def _load_user_config() -> dict:
    """加载用户自定义配置"""
    if os.path.exists(USER_CONFIG_PATH):
        try:
            with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_user_config(config: dict):
    """保存用户自定义配置"""
    os.makedirs(os.path.dirname(USER_CONFIG_PATH), exist_ok=True)
    with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_config() -> dict:
    """获取完整配置（默认 + 用户覆盖）"""
    user = _load_user_config()
    config = deepcopy(DEFAULT_CONFIG)

    # 递归合并用户覆盖
    def _merge(base, override):
        for key, val in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(val, dict):
                _merge(base[key], val)
            else:
                base[key] = val

    _merge(config, user)
    return config


def update_config(updates: dict) -> dict:
    """更新配置项，返回完整配置"""
    user = _load_user_config()
    _merge_dict(user, updates)
    _save_user_config(user)
    return get_config()


def _merge_dict(base: dict, updates: dict, path: list = None):
    """递归合并字典"""
    if path is None:
        path = []
    for key, val in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _merge_dict(base[key], val, path + [str(key)])
        else:
            base[key] = val


def reset_config() -> dict:
    """重置为默认配置"""
    if os.path.exists(USER_CONFIG_PATH):
        os.remove(USER_CONFIG_PATH)
    return deepcopy(DEFAULT_CONFIG)


def apply_user_config():
    """将用户配置应用到运行时（修改 config 模块的变量）"""
    user = _load_user_config()
    if not user:
        return

    from . import config as cfg

    # 行业评分权重
    iw = user.get("industry_weights", {})
    for key in cfg.INDUSTRY_WEIGHTS:
        if key in iw and isinstance(iw[key], dict):
            cfg.INDUSTRY_WEIGHTS[key] = float(iw[key]["value"])

    # 个股评分权重
    sw = user.get("stock_weights", {})
    for key in cfg.STOCK_WEIGHTS:
        if key in sw and isinstance(sw[key], dict):
            cfg.STOCK_WEIGHTS[key] = float(sw[key]["value"])

    # 选股参数
    sp = user.get("selection_params", {})
    if isinstance(sp.get("top_n"), dict):
        cfg.TOP_N_FINAL = int(sp["top_n"]["value"])
    if isinstance(sp.get("max_per_industry"), dict):
        cfg.MAX_PER_INDUSTRY = int(sp["max_per_industry"]["value"])
    if isinstance(sp.get("candidates_per_industry"), dict):
        cfg.CANDIDATES_PER_INDUSTRY = int(sp["candidates_per_industry"]["value"])
    if isinstance(sp.get("industry_boost_ratio"), dict):
        cfg.INDUSTRY_BOOST_RATIO = float(sp["industry_boost_ratio"]["value"])

    # 市场阈值
    mt = user.get("market_thresholds", {})
    for state in ["strong", "neutral", "weak"]:
        if state in mt and isinstance(mt[state], dict):
            ratio = mt[state].get("positive_ratio_min")
            count = mt[state].get("industry_count")
            if ratio is not None and count is not None:
                cfg.MARKET_THRESHOLDS[state] = (float(ratio), int(count))

    print("User config applied.")
