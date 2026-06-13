"""新闻驱动 — 自动抓取财经热点，映射到申万行业，动态更新事件评分

用法：
  from stock_analyzer.analysis.news_driver import update_event_sectors
  update_event_sectors()  # 在 V3 策略运行前调用
"""
import time
from datetime import datetime
from typing import Optional

# 热点关键词 → 申万二级行业代码映射
# 当新闻/热点中出现这些关键词时，对应行业的事件分和曝光度会提升
KEYWORD_TO_INDUSTRY = {
    # 科技
    "半导体": "2701", "芯片": "2701", "集成电路": "2701", "光刻": "2701", "存储": "2701",
    "AI": "7104", "人工智能": "7104", "大模型": "7104", "数字经济": "7104", "金融科技": "7104",
    "机器人": "2802", "人形机器人": "2802", "自动化": "2802",
    "低空经济": "6505", "无人机": "6505",
    "商业航天": "6502", "航天": "6502", "SpaceX": "6502", "卫星": "6307",
    "6G": "6307", "通信": "6307",
    
    # 新能源
    "固态电池": "6307", "电池": "6307", "锂电池": "6307", "新能源汽车": "2802",
    "光伏": "6403", "储能": "6307",
    
    # 金融
    "券商": "4901", "证券": "4901", "牛市": "4901", "成交量": "4901",
    
    # 周期
    "黄金": "2404", "贵金属": "2404", "金价": "2404",
    "铜": "2403", "工业金属": "2403", "有色金属": "2403",
    "稀土": "2405", "小金属": "2405",
    
    # 消费
    "白酒": "3402", "消费": "3402", "食品": "3402",
    "医药": "3701", "创新药": "3701", "医疗": "3705",
    
    # 军工
    "军工": "6505", "国防": "6505", "军贸": "6505",
}


def fetch_hot_keywords() -> list:
    """从 akshare 获取当日热点关键词"""
    try:
        import akshare as ak
        df = ak.stock_hot_keyword_em()
        if df is not None and not df.empty:
            # 第二列是关键词
            keywords = df.iloc[:, 1].tolist()
            return [str(k).strip() for k in keywords if k]
    except Exception:
        pass
    return []


def fetch_hot_stocks() -> list:
    """从 akshare 获取当日热门股票及所属板块"""
    try:
        import akshare as ak
        df = ak.stock_hot_rank_em()
        if df is not None and not df.empty:
            # 返回热门股票列表
            stocks = []
            for _, row in df.iterrows():
                name = str(row.iloc[1]) if len(row) > 1 else ""
                stocks.append(name)
            return stocks
    except Exception:
        pass
    return []


def analyze_hot_sectors(keywords: list, stock_names: list) -> dict:
    """分析热点关键词和热门股票，返回行业代码→热度分的映射

    返回: {"2701": 85, "6502": 70, ...}
    """
    sector_scores = {}

    # 1. 关键词匹配
    for keyword in keywords:
        for pattern, ind_code in KEYWORD_TO_INDUSTRY.items():
            if pattern.lower() in keyword.lower():
                current = sector_scores.get(ind_code, 0)
                # 每次匹配增加热度
                sector_scores[ind_code] = min(current + 25, 100)
                break

    # 2. 通过热门股票名称推断行业
    for name in stock_names:
        for pattern, ind_code in KEYWORD_TO_INDUSTRY.items():
            if pattern.lower() in name.lower():
                current = sector_scores.get(ind_code, 0)
                sector_scores[ind_code] = min(current + 15, 100)
                break

    return sector_scores


def update_event_sectors(verbose: bool = False) -> dict:
    """拉取最新新闻热点，更新 V3 事件板块评分

    返回: 更新后的事件板块字典 {l2_code: (event_score, exposure, driver, ...)}
    """
    from ..config import EVENT_SECTORS_FULL

    def log(msg):
        if verbose:
            print(f"[NewsDriver] {msg}", flush=True)

    log("Fetching hot keywords...")
    keywords = fetch_hot_keywords()
    log(f"  Got {len(keywords)} keywords")

    stock_names = fetch_hot_stocks()
    log(f"  Got {len(stock_names)} hot stocks")

    # 分析热点行业
    hot_sectors = analyze_hot_sectors(keywords, stock_names)
    log(f"  Identified {len(hot_sectors)} hot sectors: {hot_sectors}")

    if not hot_sectors:
        log("No hot sectors detected, keeping defaults")
        return dict(EVENT_SECTORS_FULL)

    # 更新 EVENT_SECTORS_FULL
    today = datetime.now().strftime("%Y-%m-%d")
    updated = {}
    for l2_code, info in EVENT_SECTORS_FULL.items():
        event_score, exposure, driver, psych_note, psych_score = info

        # 如果该行业在热点中，提升事件分
        hot_score = hot_sectors.get(l2_code, 0)
        if hot_score > 0:
            # 事件分提升到热点水平
            new_event = max(event_score, hot_score)
            # 曝光度也提升
            new_exposure = min(exposure + 10, 100)
            # 更新驱动描述
            new_driver = driver
            if hot_score >= 70:
                new_driver = f"[热门] {driver}"
            elif hot_score >= 50:
                new_driver = f"[关注] {driver}"

            updated[l2_code] = (new_event, new_exposure, new_driver, f"热点更新于 {today}", psych_score)
            log(f"  Updated {l2_code}: event {event_score}->{new_event}, exposure {exposure}->{new_exposure}")
        else:
            # 非热点行业，事件分随时间衰减
            decayed = max(event_score - 2, 20)  # 每次跑减2分，最低20
            updated[l2_code] = (decayed, exposure, driver, psych_note, psych_score)

    # 如果有新的热点行业不在原列表中，添加它
    # （需要反查 keyword_to_industry 获取行业名称，这里简化处理）
    for l2_code, hot_score in hot_sectors.items():
        if l2_code not in updated and hot_score >= 50:
            # 查找行业名称
            ind_name = _get_industry_name(l2_code)
            if ind_name:
                updated[l2_code] = (hot_score, hot_score, f"[自动发现] {ind_name} 热点", f"热点更新于 {today}", 50)
                log(f"  Added new sector: {l2_code} {ind_name} (hot score: {hot_score})")

    # 写回 EVENT_SECTORS_FULL
    EVENT_SECTORS_FULL.clear()
    EVENT_SECTORS_FULL.update(updated)

    log(f"Update complete. {len(updated)} sectors total.")
    return updated


def _get_industry_name(l2_code: str) -> Optional[str]:
    """根据二级行业代码获取行业名称"""
    try:
        from ..data.loader import _load_industry_names
        names = _load_industry_names()
        return names.get(l2_code)
    except Exception:
        return None


def get_hot_sectors_summary() -> list:
    """获取当前热点行业摘要（供前端显示）"""
    from ..config import EVENT_SECTORS_FULL
    result = []
    for l2_code, info in EVENT_SECTORS_FULL.items():
        event_score = info[0]
        driver = info[2] if len(info) > 2 else ""
        if "[热门]" in driver or "[关注]" in driver:
            result.append({
                "code": l2_code,
                "score": event_score,
                "driver": driver.replace("[热门] ", "").replace("[关注] ", ""),
                "hot": "[热门]" in driver,
            })
    return sorted(result, key=lambda x: x["score"], reverse=True)
