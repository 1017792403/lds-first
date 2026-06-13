"""数据缓存层 — SQLite 缓存

减少重复 API 请求：
- 行业分类数据：缓存 7 天
- K 线数据：缓存 1 天，增量更新
"""
import os
import json
import sqlite3
import time
import pandas as pd
from typing import Optional, Any
from ..config import TEMP

CACHE_DB = os.path.join(TEMP, "stock_cache.db")

# 缓存有效期（秒）
TTL = {
    "industry": 7 * 86400,     # 行业分类 7 天
    "kline": 1 * 86400,        # K 线 1 天
    "quote": 300,              # 行情快照 5 分钟
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(CACHE_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS cache (
        key TEXT PRIMARY KEY,
        value TEXT,
        expires_at REAL
    )""")
    return conn


def get(key: str) -> Optional[Any]:
    """读取缓存，过期返回 None"""
    conn = get_conn()
    row = conn.execute(
        "SELECT value, expires_at FROM cache WHERE key=?",
        (key,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    value, expires_at = row
    if time.time() > expires_at:
        return None
    return json.loads(value)


def set(key: str, value: Any, ttl: float):
    """写入缓存"""
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
        (key, json.dumps(value, ensure_ascii=False), time.time() + ttl),
    )
    conn.commit()
    conn.close()


def clear_expired():
    """清理过期缓存"""
    conn = get_conn()
    conn.execute("DELETE FROM cache WHERE expires_at < ?", (time.time(),))
    conn.commit()
    conn.close()


def clear_all():
    """清空全部缓存"""
    conn = get_conn()
    conn.execute("DELETE FROM cache")
    conn.commit()
    conn.close()


# ============ 高层缓存接口 ============

def cache_industry_data(df: pd.DataFrame):
    """缓存行业分类 DataFrame"""
    set("industry_data", df.to_dict(orient="records"), TTL["industry"])


def load_cached_industry() -> Optional[pd.DataFrame]:
    """读取缓存的行业分类"""
    data = get("industry_data")
    if data is not None:
        return pd.DataFrame(data)
    return None


def cache_kline(tc: str, klines: list):
    """缓存单只股票的 K 线"""
    set(f"kline:{tc}", klines, TTL["kline"])


def load_cached_kline(tc: str) -> Optional[list]:
    """读取缓存的 K 线"""
    return get(f"kline:{tc}")


def cache_quotes(quotes_df: pd.DataFrame):
    """缓存行情快照"""
    set("quotes_snapshot", quotes_df.to_dict(orient="records"), TTL["quote"])


def load_cached_quotes() -> Optional[pd.DataFrame]:
    """读取缓存的行情快照"""
    data = get("quotes_snapshot")
    if data is not None:
        return pd.DataFrame(data)
    return None


def get_cache_stats() -> dict:
    """获取缓存统计信息"""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    expired = conn.execute(
        "SELECT COUNT(*) FROM cache WHERE expires_at < ?",
        (time.time(),),
    ).fetchone()[0]
    conn.close()
    return {"total_keys": total, "expired_keys": expired}
