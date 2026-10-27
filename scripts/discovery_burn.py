"""Discovery 候補A: 焼失地の「幽霊建物」。

仮説: 近年の大規模焼失 tract では、Overture(とその 6 割を占める Microsoft ML 由来の足跡)が
焼失前の建物を数え続けており、ACS 住宅戸数に対する建物数の比が焼失していない tract より膨らむ。
基準側(MS 建物)も同じ足跡なので、building_gap はこの過大計上を検出できない。

真因ならほかに何が起きるか(予測):
  1. 比の膨張は「焼失が 2018 年以降」かつ「焼失率が高い」tract に集中する
  2. 膨張分は ML 由来の足跡が担い、OSM 由来ではあまり起きない(OSM は手で消される)
  3. 焼失が古い(2000 年代以前)tract では膨張しない(建て直し・足跡更新が済んでいる)

使い方: python scripts/discovery_burn.py [region]   # 既定 northern-ca
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import connect, strata  # noqa: E402

COLS = ["GEOID", "pop_total", "ur_class", "nifc_wildfire_burned_pct_land", "nifc_wildfire_last_year",
        "nifc_wildfire_burned_pct_land_2015_2025", "nifc_wildfire_burned_pct_land_2020_2025"]


def load(region: str) -> pd.DataFrame:
    f = pd.read_parquet(ROOT / "data" / "processed" / f"features_{region}.parquet")
    con = connect(threads=2)
    nifc = con.sql(f"""SELECT GEOID, nifc_wildfire_last_year, nifc_wildfire_burned_pct_land,
                              nifc_wildfire_burned_pct_land_2015_2025, nifc_wildfire_burned_pct_land_2020_2025
                       FROM {strata(region, 'nifc-tract-table')}""").df()
    base = con.sql(f"SELECT GEOID, pop_total, ur_class FROM {strata(region)}").df()
    return f.merge(base, on="GEOID", how="left").merge(nifc, on="GEOID", how="left")


def boot_ci(x: np.ndarray, y: np.ndarray, n: int = 2000, seed: int = 0) -> tuple[float, float]:
    """中央値の差 (x - y) のブートストラップ95%区間。"""
    rng = np.random.default_rng(seed)
    d = [np.median(rng.choice(x, len(x))) - np.median(rng.choice(y, len(y))) for _ in range(n)]
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def main() -> None:
    region = sys.argv[1] if len(sys.argv) > 1 else "northern-ca"
    d = load(region)
    d = d[d["housing_units"] > 0].copy()
    # 交絡: 焼失 tract は農村に偏り、農村は付属建物で比が大きい。層を固定して比べる
    ur = sys.argv[2] if len(sys.argv) > 2 else "Rural"
    print("ur_class 内訳:", d["ur_class"].value_counts().to_dict(), "→ 対象:", ur)
    if ur != "all":
        d = d[d["ur_class"] == ur].copy()
    d["ratio_all"] = d["bldg_n"] / d["housing_units"]
    d["ratio_ms"] = d["bldg_ms_n"] / d["housing_units"]
    d["ratio_osm"] = d["bldg_osm_n"] / d["housing_units"]
    burned_pct = d["nifc_wildfire_burned_pct_land_2015_2025"].fillna(0)
    last = d["nifc_wildfire_last_year"].fillna(0)
    groups = {
        "近年大規模焼失(2015-25焼失率>=30%, 最終>=2018)": (burned_pct >= 30) & (last >= 2018),
        "近年小規模焼失(2015-25焼失率 1-30%)": (burned_pct >= 1) & (burned_pct < 30),
        "古い焼失のみ(最終<2010)": (last > 0) & (last < 2010) & (burned_pct < 1),
        "焼失なし": last == 0,
    }
    ctrl = d[groups["焼失なし"]]
    rows = []
    for name, m in groups.items():
        g = d[m]
        if len(g) == 0:
            continue
        row = {"群": name, "tract数": len(g)}
        for col in ("ratio_all", "ratio_ms", "ratio_osm"):
            row[f"{col}_中央値"] = round(float(g[col].median()), 3)
        if name != "焼失なし" and len(g) >= 5:
            lo, hi = boot_ci(g["ratio_all"].to_numpy(), ctrl["ratio_all"].to_numpy())
            row["ratio_all差_95%CI"] = f"[{lo:.3f}, {hi:.3f}]"
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False))

    top = d[groups["近年大規模焼失(2015-25焼失率>=30%, 最終>=2018)"]].sort_values("ratio_all", ascending=False)
    print("\n近年大規模焼失 tract(比の大きい順, 上位15)")
    print(top[["GEOID", "housing_units", "bldg_n", "bldg_ms_n", "bldg_osm_n", "ratio_all",
               "nifc_wildfire_last_year", "nifc_wildfire_burned_pct_land_2015_2025", "ur_class"]]
          .head(15).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
