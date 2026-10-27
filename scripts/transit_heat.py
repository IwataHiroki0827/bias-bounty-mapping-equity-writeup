"""公共交通 Discovery の影響: 地図に無い停留所が、気候リスクの高い tract にどれだけあるか(配布物の strata だけで計算)。

南中部TX の strata 表(cvi_overall = 気候脆弱性指数、cvi_climate_extreme_events、gehe_wbgt30_days_mean =
湿球黒球温度 30℃超の日数)を tract に結び、Houston METRO と San Antonio VIA の停留所を数える。
「高い」は南中部TX 地域の tract の上位 25%。
使い方: python scripts/transit_heat.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402

URL = ("https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge/strata/"
       "south-central-tx/south-central-tx-strata-tract-table.csv")
COLS = ["GEOID", "cvi_overall", "cvi_climate_extreme_events", "gehe_wbgt30_days_mean"]


def main() -> None:
    txt = requests.get(URL, headers={"User-Agent": "curl/8"}, timeout=120).text
    st = pd.read_csv(io.StringIO(txt), dtype={"GEOID": str}, usecols=COLS)
    q75 = {c: st[c].quantile(0.75) for c in COLS[1:]}
    s = pd.read_parquet(ROOT / "data" / "processed" / "transit_robust.parquet")
    s = s[s["GEOID"].notna() & s["feed"].isin(["houston_metro", "via_san_antonio", "capmetro_austin", "dart_dallas"])]
    s["mapped"] = np.fmin(s["d_infra"], s["d_places"]) <= 100
    s = s.merge(st, on="GEOID", how="left")
    print("南中部TX の上位25% の閾値:", {k: round(v, 3) for k, v in q75.items()})
    rows = []
    for feed, g in s.groupby("feed"):
        un = g[~g["mapped"]]
        row = {"feed": feed, "stops": len(g), "unmapped": len(un)}
        for c in COLS[1:]:
            row[f"unmapped_in_top25_{c}"] = int((un[c] >= q75[c]).sum())
            row[f"share_top25_{c}"] = round(float((g[c] >= q75[c]).mean()), 3)
        row["wbgt30_days_mean_at_unmapped"] = round(float(un["gehe_wbgt30_days_mean"].mean()), 1) if len(un) else None
        rows.append(row)
    out = pd.DataFrame(rows).set_index("feed").T
    pd.set_option("display.width", 200)
    print(out.to_string())


if __name__ == "__main__":
    main()
