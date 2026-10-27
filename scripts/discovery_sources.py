"""Discovery 候補B: 基準データの循環(建物の上流データセットの偏り)。

採点の building_gap は「Overture 棟数 / Microsoft 棟数」。Overture の建物の多くは Microsoft ML 由来なので、
ML 由来の割合が高い tract ほど、ギャップは構造的に 0 に近づき、実世界の網羅度を測れなくなる。
この割合が層(都市農村・部族・SVI)でどう偏るかを測る。

使い方: python scripts/discovery_sources.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, strata  # noqa: E402

N_EXPECTED = {"eastern-ok": 1192, "eastern-wa": 415, "maricopa-az": 1593, "northern-ca": 591, "south-central-tx": 6003}


def load_all() -> pd.DataFrame:
    con = connect(threads=4)
    frames = []
    for reg in REGIONS:
        f = pd.read_parquet(ROOT / "data" / "processed" / f"features_{reg}.parquet")
        if len(f) != N_EXPECTED[reg] or f["GEOID"].duplicated().any():
            raise SystemExit(f"{reg}: 行数 {len(f)} が期待 {N_EXPECTED[reg]} と不一致、または GEOID 重複")
        s = con.sql(f"""SELECT GEOID, pop_total, ur_class, tribal_any, svi_overall
                        FROM {strata(reg)}""").df()
        frames.append(f.merge(s, on="GEOID", how="left"))
    return pd.concat(frames, ignore_index=True)


def share_table(d: pd.DataFrame, by: str) -> pd.DataFrame:
    g = d.groupby(["region", by], dropna=False).agg(
        tracts=("GEOID", "size"), bldg=("bldg_n", "sum"), ms=("bldg_ms_n", "sum"), osm=("bldg_osm_n", "sum"),
        named=("bldg_named_n", "sum"), unnamed_km=("road_unnamed_km", "sum"), all_km=("road_all_km", "sum"))
    g["ms_share%"] = (100 * g["ms"] / g["bldg"]).round(1)
    g["osm_share%"] = (100 * g["osm"] / g["bldg"]).round(1)
    g["road_unnamed%"] = (100 * g["unnamed_km"] / g["all_km"]).round(1)
    return g[["tracts", "bldg", "ms_share%", "osm_share%", "road_unnamed%"]]


def main() -> None:
    d = load_all()
    print("行数", len(d), "/ bldg_n 欠損", int(d["bldg_n"].isna().sum()), "/ 住宅0戸", int((d["housing_units"] == 0).sum()),
          "/ 人口0", int((d["pop_total"] == 0).sum()))
    d["svi_q"] = pd.cut(d["svi_overall"], [-0.01, 0.25, 0.5, 0.75, 1.0], labels=["Q1低", "Q2", "Q3", "Q4高"])
    d["tribal"] = d["tribal_any"].map({True: "部族", False: "非部族"})
    pd.set_option("display.width", 200)
    for by in ("ur_class", "tribal", "svi_q"):
        print(f"\n=== {by} 別 ===")
        print(share_table(d, by).to_string())
    out = ROOT / "data" / "processed" / "features_all.parquet"
    d.to_parquet(out, index=False)
    print("\n保存:", out)


if __name__ == "__main__":
    main()
