"""K线数据获取 — 并发获取 + SQLite 缓存"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
from ..config import KLINE_URL, KLINE_DEFAULT_DAYS, KLINE_TIMEOUT, KLINE_INTERVAL
from ..cache import cache_kline, load_cached_kline


def fetch_kline(tc: str, days: int = KLINE_DEFAULT_DAYS,
                use_cache: bool = True) -> list:
    """获取单只股票的日K线数据，优先读缓存。"""
    if use_cache:
        cached = load_cached_kline(tc)
        if cached is not None:
            return cached

    url = KLINE_URL.format(tc, days)
    cmd = f'curl -sk --max-time {KLINE_TIMEOUT} "{url}"'
    out = subprocess.run(cmd, shell=True, capture_output=True,
                         text=True, timeout=KLINE_TIMEOUT + 5)

    klines = []
    if out.stdout:
        try:
            data = json.loads(out.stdout)
            for key in data.get("data", {}):
                if "qfqday" in data["data"][key]:
                    klines = data["data"][key]["qfqday"]
                    break
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    if klines and use_cache:
        cache_kline(tc, klines)

    return klines


def fetch_kline_batch(tencent_codes: list, days: int = KLINE_DEFAULT_DAYS,
                      use_cache: bool = True, max_workers: int = 6,
                      interval: float = KLINE_INTERVAL, progress_cb=None) -> dict:
    """并发获取多只股票的 K 线"""
    result = {}
    total = len(tencent_codes)
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_kline, tc, days, use_cache): tc
            for tc in tencent_codes
        }

        for future in as_completed(futures):
            tc = futures[future]
            try:
                klines = future.result()
                if klines:
                    result[tc] = klines
            except Exception:
                pass
            completed += 1
            if progress_cb:
                progress_cb(completed, total)
            if interval:
                time.sleep(interval)

    return result
