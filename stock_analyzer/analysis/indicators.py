"""技术指标计算 — MACD, KDJ, 量比, 斜率, 量价背离等"""
import numpy as np
import pandas as pd
from ..data.kline import fetch_kline_batch


def calc_macd(closes: list) -> dict:
    """计算 MACD 指标。
    返回: {macd, hist, golden_cross}
    """
    result = {"macd": 0.0, "hist": 0.0, "golden_cross": False}
    if len(closes) < 26:
        return result

    s = pd.Series(closes)
    ema12 = s.ewm(span=12).mean()
    ema26 = s.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9).mean()

    result["macd"] = round(macd_line.iloc[-1], 2)
    result["hist"] = round(macd_line.iloc[-1] - signal.iloc[-1], 2)

    # 金叉判定：当前 MACD > Signal 且 前一个 MACD <= Signal
    cur = macd_line.iloc[-1]
    sig = signal.iloc[-1]
    prev = macd_line.iloc[-2] if len(macd_line) >= 2 else cur
    prev_sig = signal.iloc[-2] if len(signal) >= 2 else sig
    result["golden_cross"] = (cur > sig) and (prev <= prev_sig)
    return result


def calc_kdj(highs: list, lows: list, closes: list) -> float:
    """计算 KDJ 指标的 J 值。"""
    if len(highs) < 9 or len(lows) < 9 or len(closes) < 9:
        return 50.0

    h9 = max(highs[-9:])
    l9 = min(lows[-9:])
    if h9 == l9:
        return 50.0

    rsv = (closes[-1] - l9) / (h9 - l9) * 100
    k = rsv * 2 / 3 + 50 / 3
    d = k * 2 / 3 + 50 / 3
    j = 3 * k - 2 * d
    return round(j, 1)


def calc_volume_ratio(volumes: list, short_period: int = 5,
                      long_period: int = 10) -> float:
    """计算量比：短期均量 / 长期均量"""
    min_len = short_period + long_period
    if len(volumes) < min_len:
        return 1.0

    short_avg = np.mean(volumes[-short_period:])
    long_avg = np.mean(volumes[-(short_period + long_period):-short_period])
    if long_avg <= 0:
        return 1.0
    return round(short_avg / long_avg, 2)


def calc_slope(closes: list, period: int = 10) -> float:
    """计算价格斜率（%），衡量短期趋势强度"""
    if len(closes) < period:
        return 0.0
    x = np.arange(period)
    y = np.array(closes[-period:])
    slope = np.polyfit(x, y, 1)[0] / max(np.mean(closes[-period:]), 0.01) * 100
    return round(slope, 3)


def calc_divergence(closes: list, volumes: list, period: int = 5) -> int:
    """量价背离检测。
    返回: 1 = 量价配合（看多）, -1 = 量价背离（看空）, 0 = 正常
    """
    if len(closes) < period * 2 or len(volumes) < period * 2:
        return 0

    recent_c = np.mean(closes[-period:])
    prev_c = np.mean(closes[-(period * 2):-period])
    recent_v = np.mean(volumes[-period:])
    prev_v = np.mean(volumes[-(period * 2):-period])

    if recent_c > prev_c and recent_v < prev_v * 0.8:
        return -1  # 价涨量缩 = 背离
    if recent_c > prev_c * 1.03 and recent_v > prev_v * 1.5:
        return 1   # 价涨量增 = 配合
    return 0


def calc_ma(closes: list, period: int) -> float:
    """移动平均线"""
    if len(closes) < period:
        return round(closes[-1], 2) if closes else 0.0
    return round(np.mean(closes[-period:]), 2)


def calc_consecutive_days(closes: list, max_days: int = 5) -> dict:
    """计算连续涨跌天数"""
    cons_up = 0
    cons_down = 0
    for i in range(min(max_days, len(closes) - 1)):
        chg = (closes[-(i + 1)] / closes[-(i + 2)] - 1) * 100
        if chg > 0:
            cons_up += 1
            cons_down = 0
        else:
            cons_down += 1
            cons_up = 0
    return {"cons_up": cons_up, "cons_down": cons_down}


def calc_all_indicators(klines: list) -> dict:
    """从 Kline 数据计算全部技术指标"""
    if not klines or len(klines) < 3:
        return {}

    closes = [float(k[2]) for k in klines if len(k) >= 3]
    highs = [float(k[3]) for k in klines if len(k) >= 4]
    lows = [float(k[4]) for k in klines if len(k) >= 5]
    volumes = [float(k[5]) for k in klines if len(k) >= 6]

    if not closes:
        return {}

    macd = calc_macd(closes)
    return {
        "macd": macd["macd"],
        "hist": macd["hist"],
        "golden_cross": macd["golden_cross"],
        "kdj_j": calc_kdj(highs, lows, closes),
        "vol_ratio_s": calc_volume_ratio(volumes, 5, 10),    # 短周期量比
        "vol_ratio_l": calc_volume_ratio(volumes, 5, 15),     # 长周期量比
        "slope": calc_slope(closes),
        "divergence": calc_divergence(closes, volumes),
        "ma5": calc_ma(closes, 5),
        "ma20": calc_ma(closes, 20),
        "chg_pct": round((closes[-1] / closes[-2] - 1) * 100, 2) if len(closes) >= 2 else 0.0,
        "d5": round((closes[-1] / calc_ma(closes, 5) - 1) * 100, 1) if len(closes) >= 5 else 0.0,
        "d20": round((closes[-1] / calc_ma(closes, 20) - 1) * 100, 1) if len(closes) >= 20 else 0.0,
        "cons_up": calc_consecutive_days(closes)["cons_up"],
        "cons_down": calc_consecutive_days(closes)["cons_down"],
    }
