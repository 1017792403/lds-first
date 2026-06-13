"""结果导出 — JSON 文件输出"""
import json
from typing import List
from ..config import RESULT_JSON


def export_to_json(selected: list, market_info: dict,
                   model_version: str, output_path: str = RESULT_JSON):
    """将选股结果导出为 JSON 文件"""
    picks = []
    for i, s in enumerate(selected):
        picks.append(_pick_to_dict(i + 1, s))

    result = {
        "model_version": model_version,
        "market_summary": {
            "stocks_tracked": market_info.get("stock_count", 0),
            "positive_industries_ratio": market_info.get("positive_ratio", 0),
        },
        "picks": picks,
    }

    if "event_analysis" in market_info:
        result["event_analysis"] = market_info["event_analysis"]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return output_path


def _pick_to_dict(rank: int, s) -> dict:
    """将单只股票选股结果转为字典"""
    return {
        "rank": rank,
        "name": s.get("name", s.get("name_y", "?")),
        "code": s.get("stock_code", s.get("code", "?")),
        "industry": s.get("ind_name", s.get("industry", "?")),
        "price": float(s.get("price", s.get("price_x", s.get("p", 0)))),
        "change_pct": float(s.get("change_pct", s.get("chg", 0))),
        "score": round(float(s.get("final_score", s.get("final", 0))), 1),
        "estimated_upside": _calc_upside(s),
        "probability": _calc_prob(s),
        "logic": _get_logic_str(s),
    }


def _calc_upside(s) -> str:
    change = float(s.get("change_pct", s.get("chg", 0)))
    est = max(abs(change) * 0.4 + 1.5, 2.5)
    return f"{est:.1f}-{est * 1.5:.1f}%"


def _calc_prob(s) -> str:
    score = float(s.get("final_score", s.get("final", 0)))
    prob = min(50 + score * 0.15, 80)
    return f"{prob:.0f}%"


def _get_logic_str(s) -> str:
    if "logic" in s:
        return s["logic"]
    change = float(s.get("change_pct", s.get("chg", 0)))
    rel = float(s.get("rel_strength", 0))
    vol = float(s.get("vol_ratio", 0))
    parts = []
    if change > 3:
        parts.append(f"当日强势({change:+.1f}%)")
    if rel > 0:
        parts.append("领涨板块")
    if vol > 1.2:
        parts.append(f"放量{vol:.1f}倍")
    return " + ".join(parts) if parts else "板块龙头"
