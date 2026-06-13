"""Console output formatting"""
from typing import List


def print_header(title: str, width: int = 70):
    print()
    print("=" * width)
    print(f"{title:^{width}}")
    print("=" * width)


def print_market_summary(stock_count: int, rising_count: int,
                         positive_industries: int, total_industries: int):
    print()
    print("MARKET SUMMARY")
    print(f"  Total stocks: {stock_count}")
    print(f"  Rising: {rising_count}")
    print(f"  Falling: {stock_count - rising_count}")
    print(f"  Strong sectors: {positive_industries}/{total_industries}")


def print_industry_scores(top_industries, max_rows: int = 15):
    print(f"\n  Top {len(top_industries)} industries:")
    for _, row in top_industries.iterrows():
        print(f"    {row['l2_code']} {row['ind_name']:12s} | "
              f"Score:{row['score']:.0f} | "
              f"Avg:{row['avg_chg']:+.2f}% | "
              f"Rise:{row.get('rise_ratio', 0):.0%}")


def print_picks(selected: list, market_note: str = ""):
    print_header(f"TOP {len(selected)} PICKS", 75)
    for i, s in enumerate(selected):
        _print_single_pick(i + 1, s)
    if market_note:
        print(f"\n  [NOTE] {market_note}")


def _print_single_pick(rank: int, s):
    name = s.get("name", s.get("name_y", "?"))
    code = s.get("stock_code", s.get("code", "?"))
    industry = s.get("ind_name", s.get("industry", "?"))
    change = float(s.get("change_pct", s.get("chg_pct", s.get("chg", 0))))
    price = float(s.get("price", s.get("price_x", s.get("p", 0))))
    score = float(s.get("final_score", s.get("final", 0)))
    rel = float(s.get("rel_strength", s.get("rel_str", 0)))
    vol = float(s.get("vol_ratio", 0))

    prob = min(50 + score * 0.15, 80)
    est = max(abs(change) * 0.4 + 1.5, 2.5)
    logic_parts = _build_logic(change, rel, vol)
    logic = " + ".join(logic_parts) if logic_parts else "sector leader"

    print(f"\n  {rank}. {name} ({code})")
    print(f"     Sector: {industry}")
    print(f"     Price: {price:.2f}  |  Change: {change:+.2f}%")
    print(f"     Score: {score:.0f}  |  Rel.Strength: {rel:+.2f}%  |  Vol.Ratio: {vol:.1f}x")
    print(f"     Est.Upside: {est:.1f}-{est * 1.5:.1f}%  |  Prob: {prob:.0f}%")
    print(f"     Logic: {logic}")

    if "overheat_penalty" in s:
        print(f"     Overheat Penalty: {float(s['overheat_penalty']):.1f}")
    if has_tech_info(s):
        print(f"     MACD:{s.get('macd', 0):+.1f}  GC:{'Y' if s.get('golden_cross', s.get('golden', False)) else 'N'}  "
              f"KDJ(J):{s.get('kdj_j', 50):.0f}")
    if "buy_conditions" in s:
        for bc in s["buy_conditions"]:
            print(f"     BUY: {bc}")
    if "sell_conditions" in s:
        for sc in s["sell_conditions"]:
            print(f"     SELL: {sc}")


def _build_logic(change: float, rel_strength: float, vol_ratio: float) -> list:
    parts = []
    if change > 3:
        parts.append(f"Strong({change:+.1f}%)")
    elif change > 1:
        parts.append(f"Steady({change:+.1f}%)")
    if rel_strength > 0:
        parts.append("Leading sector")
    if vol_ratio > 2:
        parts.append(f"Vol{vol_ratio:.0f}x")
    elif vol_ratio > 1.2:
        parts.append("Vol confirmed")
    if change > 0:
        parts.append("Capital inflow")
    return parts


def has_tech_info(s) -> bool:
    return any(k in s for k in ["macd", "kdj_j", "golden_cross", "golden"])


def print_summary_table(selected: list):
    print(f"\n{'=' * 95}")
    print(f"{'#':<3} {'Code':<8} {'Industry':<14} {'Close':<8} {'Chg%':<8} "
          f"{'Score':<6} {'Est.Upside':<12}")
    print(f"{'-' * 95}")
    for s in selected:
        code = s.get("stock_code", s.get("code", "?"))
        industry = s.get("ind_name", s.get("industry", "?"))
        price = float(s.get("price", s.get("price_x", 0)))
        change = float(s.get("change_pct", s.get("chg", 0)))
        score = float(s.get("final_score", s.get("final", 0)))
        est = max(abs(change) * 0.4 + 1.5, 2.5)
        a = "+" if change > 0 else ""
        print(f"{s.get('rank', '?'):<3} {code:<8} {industry:<14} "
              f"{price:<8.2f} {a}{change:.2f}%{'':<3} "
              f"{score:<6.0f} {est:.1f}-{est * 1.5:.1f}%")
