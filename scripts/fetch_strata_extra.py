"""配布 strata 表(5地域、計約 24MB の CSV)から、特徴に使う少数の列だけを取り出して保存する。

使う列: 陸域面積(ALAND)、都市人口の割合(pct_urban)、郡の都市化区分(NCHS 2013、RUCC 2023)。
建物数の列(usfs_BuildingCount_sum・carbonplan_buildings)は、撤去された建物の足跡から作られている可能性があるので使わない。
元の CSV は保存しない(列を取り出したら捨てる)。

出力: data/processed/strata_extra.parquet
使い方: python scripts/fetch_strata_extra.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402

BASE = "https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge/strata"
REGIONS = ["eastern-ok", "eastern-wa", "maricopa-az", "northern-ca", "south-central-tx"]
COLS = ["GEOID", "ALAND", "pct_urban", "nchs_2013", "rucc_2023"]


def main() -> None:
    parts = []
    for r in REGIONS:
        url = f"{BASE}/{r}/{r}-strata-tract-table.csv"
        text = requests.get(url, headers={"User-Agent": "curl/8"}, timeout=300).text
        df = pd.read_csv(io.StringIO(text), dtype={"GEOID": str}, usecols=COLS)
        parts.append(df)
        print(r, len(df))
    out = pd.concat(parts).drop_duplicates("GEOID")
    path = ROOT / "data" / "processed" / "strata_extra.parquet"
    out.to_parquet(path, index=False)
    print("保存:", path, len(out))


if __name__ == "__main__":
    main()
