"""10/24: 採点の偏りの指標(Zindi の public_scoring_rubric: 山火事・夏の暑熱・干ばつ・CVI)に当たる strata の列を tract ごとに取る。

目的: 基準の推定が、公式の偏りの指標で区切った tract で系統的にずれているかを、単独のプローブで測る(writeup の Discovery の証拠)。
出力: data/processed/strata_hazard.parquet(全地域を1ファイル、上書き)
使い方: python scripts/build_strata_hazard.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, strata  # noqa: E402

OUT = ROOT / "data" / "processed" / "strata_hazard.parquet"
COLS = ["usfs_WHP_mean", "epht_heat_days_summer", "usdm_summer_dsci", "usdm_winter_dsci", "cvi_overall"]


def main() -> None:
    t0 = time.time()
    con = connect(threads=2)
    con.sql("SET memory_limit = '512MB'")
    sel = ", ".join(COLS)
    df = pd.concat([con.sql(f"SELECT GEOID, {sel} FROM {strata(r)}").df() for r in REGIONS])
    df.to_parquet(OUT, index=False)
    print(f"rows={len(df)} " + " ".join(f"{c}:na={df[c].isna().mean():.2f}" for c in COLS) + f" {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
