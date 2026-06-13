"""行情拉取 — 支持并发+缓存

从串行 curl 改为 ThreadPoolExecutor 并发拉取，配合缓存层减少重复请求。
"""
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import pandas as pd
from ..config import QUOTE_URL, QUOTE_BATCH_SIZE, QUOTE_TIMEOUT, QUOTE_INTERVAL
from ..cache import get, set, TTL


def fetch_quotes(tencent_codes: list, batch_size: int = QUOTE_BATCH_SIZE,
                 use_cache: bool = True, max_workers: int = 8,
                 interval: float = QUOTE_INTERVAL, progress_cb=None) -> pd.DataFrame:
    """批量拉取腾讯实时行情（多线程并发）。

    支持缓存：5 分钟内不重复拉取同一批股票。
    """
    # 尝试从缓存加载
    cache_key = f"quotes:{hash(tuple(sorted(tencent_codes[:100])))}"
    if use_cache:
        cached = get("quotes_snapshot")
        if cached is not None:
            return pd.DataFrame(cached)

    results = {}
    total = len(tencent_codes)
    batches = [tencent_codes[i:i + batch_size]
               for i in range(0, total, batch_size)]
    completed = 0

    def fetch_batch(batch_codes):
        query = ",".join(batch_codes)
        cmd = f'curl -sk --max-time {QUOTE_TIMEOUT} "{QUOTE_URL.format(query)}"'
        out = subprocess.run(cmd, shell=True, capture_output=True,
                             text=True, timeout=QUOTE_TIMEOUT + 5)
        batch_results = {}
        if out.returncode == 0 and out.stdout:
            _parse_quotes_response(out.stdout, batch_results)
        return batch_results

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_batch, b): b for b in batches}

        for future in as_completed(futures):
            batch_results = future.result()
            results.update(batch_results)
            completed += 1
            if progress_cb:
                progress_cb(min(completed * batch_size, total), total)
            time.sleep(interval)  # 小幅间隔避免被封

    # 组装 DataFrame
    if not results:
        return pd.DataFrame()

    qdf = pd.DataFrame.from_dict(results, orient="index").reset_index()
    qdf.columns = ["tc", "name", "price", "prev_close",
                   "change_pct", "volume", "amount"]
    for col in ["price", "prev_close", "change_pct", "volume", "amount"]:
        qdf[col] = pd.to_numeric(qdf[col], errors="coerce")
    qdf = qdf.dropna(subset=["price", "change_pct"])

    # 写入缓存
    if use_cache:
        from ..cache import cache_quotes
        cache_quotes(qdf)

    return qdf


def _parse_quotes_response(text: str, result_dict: dict):
    """解析腾讯 API 返回的文本，写入 result_dict"""
    for line in text.strip().split(";"):
        line = line.strip()
        if not line or "none_match" in line or "~" not in line:
            continue
        parts = line.split("~")
        if len(parts) < 40:
            continue

        raw = parts[0].replace("v_", "").strip()
        code_key = re.sub(r'="\d+"?$', "", raw).strip()

        try:
            name = parts[1].encode("latin1").decode("gbk")
        except Exception:
            name = parts[1]

        result_dict[code_key] = {
            "name": name,
            "price": parts[3],
            "prev_close": parts[4],
            "change_pct": parts[32],
            "volume": parts[6],
            "amount": parts[37] if len(parts) > 37 else "0",
        }
