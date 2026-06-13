"""数据加载 — 申万行业分类 + 行业名称映射"""
import os
import json
import pandas as pd
import akshare as ak
from ..config import SW_XLS


def _find_classification_file() -> str:
    """查找可用的行业分类数据文件，优先 xls 再找 json"""
    if os.path.exists(SW_XLS):
        return SW_XLS
    # 尝试项目目录下的 data/sw.json
    for p in [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "sw.json"),
        os.path.join(os.getcwd(), "data", "sw.json"),
    ]:
        if os.path.exists(p):
            return p
    return SW_XLS  # fallback，让调用方处理错误


def load_sw_classification(xls_path: str = None) -> pd.DataFrame:
    """加载申万行业分类，支持 xls 和 json 两种格式。

    字段: stock_code, entry_date, industry_code, update_date, l2_code, ind_name, tc
    """
    if xls_path is None:
        xls_path = _find_classification_file()

    ext = os.path.splitext(xls_path)[1].lower()

    if ext == ".json":
        with open(xls_path, "r", encoding="utf-8") as f:
            records = json.load(f)
        df = pd.DataFrame(records)
        df.columns = ["stock_code", "entry_date", "industry_code", "update_date"]
        df["entry_date"] = pd.to_datetime(df["entry_date"], errors="coerce")
    else:
        df = pd.read_excel(xls_path, dtype={"股票代码": str, "行业代码": str})
        df.columns = ["stock_code", "entry_date", "industry_code", "update_date"]
        df["entry_date"] = pd.to_datetime(df["entry_date"], errors="coerce")

    # 取每只股票的最新分类
    latest = df.sort_values("entry_date").groupby("stock_code").last().reset_index()
    latest["l2_code"] = latest["industry_code"].str[:4]

    # 加载行业名称
    name_map = _load_industry_names()
    latest["ind_name"] = latest["l2_code"].map(name_map)
    latest = latest.dropna(subset=["ind_name"])

    # 生成腾讯行情代码
    latest["tc"] = latest["stock_code"].apply(_to_tencent_code)
    return latest


def _load_industry_names() -> dict:
    """从 akshare 加载申万二级行业名称映射 {num_code: name}"""
    cninfo = ak.stock_industry_category_cninfo(symbol="申银万国行业分类标准")
    cninfo.columns = ["code", "name", "end_date", "ind_type",
                      "ind_type_id", "name_en", "parent", "level"]
    level2 = cninfo[cninfo["level"] == 2].copy()
    level2["num_code"] = level2["code"].str.replace(r"^S", "", regex=True)
    return dict(zip(level2["num_code"], level2["name"]))


def _to_tencent_code(code: str) -> str:
    """股票代码 → 腾讯行情格式 (sh/sz + 6位代码)"""
    code = str(code).zfill(6)
    return f"sh{code}" if code.startswith(("6", "9")) else f"sz{code}"
