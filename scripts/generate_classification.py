#!/usr/bin/env python3
"""生成行业分类数据（供 GitHub Actions 使用）

在本地运行一次：python scripts/generate_classification.py
会把 sw.xls 中的数据导出为 data/sw.json 提交到仓库，
这样 GitHub Actions 就能直接用，不需要 sw.xls。
"""
import os
import sys
import json
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_analyzer.config import SW_XLS

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_from_excel():
    """从本地 sw.xls 生成 JSON"""
    if not os.path.exists(SW_XLS):
        print(f"sw.xls not found at {SW_XLS}")
        return None

    print(f"Reading {SW_XLS}...")
    df = pd.read_excel(SW_XLS, dtype={"股票代码": str, "行业代码": str})
    df.columns = ["stock_code", "entry_date", "industry_code", "update_date"]
    df["entry_date"] = pd.to_datetime(df["entry_date"], errors="coerce").astype(str)
    df["update_date"] = pd.to_datetime(df["update_date"], errors="coerce").astype(str)

    data = df.to_dict(orient="records")
    output_path = os.path.join(OUTPUT_DIR, "sw.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Generated {output_path}: {len(data)} records")
    return output_path


def generate_from_akshare():
    """尝试从 akshare 在线生成"""
    try:
        import akshare as ak

        # 获取申万行业分类
        print("Fetching industry classification from akshare...")
        cninfo = ak.stock_industry_category_cninfo(symbol="申银万国行业分类标准")
        cninfo.columns = ["code", "name", "end_date", "ind_type",
                          "ind_type_id", "name_en", "parent", "level"]
        level2 = cninfo[cninfo["level"] == 2]
        level2["num_code"] = level2["code"].str.replace(r"^S", "", regex=True)
        print(f"  Got {len(level2)} level-2 industries")

        # 这里需要实际的股票→行业映射数据
        # 目前 akshare 没有直接的申万全量映射 API
        # 需要从 sw.xls 提供
        print("  Note: This only generates industry names, not stock mappings.")
        print("  The full stock-to-industry mapping requires sw.xls or sw.json.")
        return None

    except ImportError:
        print("akshare not installed")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    # 优先从本地 sw.xls 生成
    result = generate_from_excel()
    if result is None:
        print("\nsw.xls not found. Attempting akshare fallback...")
        result = generate_from_akshare()

    if result:
        print(f"\nDone. Commit data/sw.json to your repo.")
    else:
        print(f"\nCould not generate sw.json.")
        print(f"Please run this script on your local machine where sw.xls exists:")
        print(f"  python scripts/generate_classification.py")
        print(f"Then commit the generated data/sw.json to your repo.")
