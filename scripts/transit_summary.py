"""transit_robust.parquet を、採点対象の tract 内にある停留所だけに絞って集計する。

範囲外の停留所は Overture の抽出範囲外なので必ず「未収載」になる。絞らないと率が不当に下がる。
使い方: python scripts/transit_summary.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402

R = 100


def main() -> None:
    d = pd.read_parquet(ROOT / "data" / "processed" / "transit_robust.parquet")
    print("範囲外(tract なし)の停留所:", d.groupby("feed")["GEOID"].apply(lambda s: int(s.isna().sum())).to_dict())
    d = d[d["GEOID"].notna()].copy()
    d["mapped"] = (d["d_infra"] <= R) | (d["d_places"] <= R)
    d["svi_q"] = pd.cut(d["svi_overall"], [-0.01, 0.25, 0.5, 0.75, 1.0], labels=["Q1低", "Q2", "Q3", "Q4高"])
    pd.set_option("display.width", 200)
    print(f"\n=== 事業者別 収載率(半径 {R} m, infrastructure または places)")
    print(d.groupby(["region", "feed"])["mapped"].agg(["size", "mean"]).round(3).to_string())
    print("\n=== 事業者 × SVI 四分位")
    print(d.pivot_table(index="feed", columns="svi_q", values="mapped", aggfunc="mean", observed=True).round(3).to_string())
    print("\n=== 事業者 × 都市農村")
    print(d.pivot_table(index="feed", columns="ur_class", values="mapped", aggfunc="mean", observed=True).round(3).to_string())
    # 影響の規模: 車を持たない世帯(ACS 2020-2024 B08201、外部データ。Discovery 専用)
    acs_path = ROOT / "data" / "raw" / "ext" / "acs_vehicles.parquet"
    if acs_path.exists():
        acs = pd.read_parquet(acs_path)
        t = d.groupby(["feed", "GEOID"]).agg(stops=("mapped", "size"), mapped=("mapped", "mean")).reset_index()
        t = t.merge(acs, on="GEOID", how="left")
        t["noveh_share"] = t["hh_no_vehicle"] / t["hh_total"]
        rows = []
        for feed, g in t.groupby("feed"):
            maj = g[g["mapped"] < 0.5]
            rows.append({"feed": feed, "tracts": len(g), "車なし世帯(停留所のある tract)": int(g["hh_no_vehicle"].sum()),
                         "過半未収載 tract": len(maj), "その車なし世帯": int(maj["hh_no_vehicle"].sum()),
                         "車なし率と収載率の相関": round(float(g[["noveh_share", "mapped"]].corr().iloc[0, 1]), 3)
                         if len(g) > 5 else None})
        print("\n=== 影響の規模(車を持たない世帯)")
        print(pd.DataFrame(rows).to_string(index=False))
        t.to_parquet(ROOT / "data" / "processed" / "transit_tracts.parquet", index=False)
    print("\n=== 部族地域(aiannh_name)別、停留所 20 以上")
    g = d[d["aiannh_name"].notna()].groupby(["aiannh_name", "feed"])["mapped"].agg(["size", "mean"])
    print(g[g["size"] >= 20].round(3).to_string())


if __name__ == "__main__":
    main()
