"""writeup 用の具体例: 車なし世帯が多いのに停留所が載っていない tract、地域別の要約値。

使い方: python scripts/transit_examples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402

P = ROOT / "data" / "processed"


def main() -> None:
    t = pd.read_parquet(P / "transit_tracts.parquet")
    s = pd.read_parquet(P / "transit_robust.parquet")
    s = s[s["GEOID"].notna()]
    s["mapped"] = (s["d_infra"] <= 100) | (s["d_places"] <= 100)
    st = pd.read_parquet(P / "features_all.parquet")[["GEOID", "svi_overall", "ur_class", "pop_total"]]
    t = t.merge(st, on="GEOID", how="left")
    pd.set_option("display.width", 220)
    for feed in ("via_san_antonio", "houston_metro"):
        print(f"=== {feed}: 車なし世帯が多く、停留所の過半が未収載の tract(上位12)")
        v = t[(t.feed == feed) & (t.mapped < 0.5)].sort_values("hh_no_vehicle", ascending=False)
        print(v[["GEOID", "stops", "mapped", "hh_total", "hh_no_vehicle", "noveh_share", "svi_overall"]].head(12).round(3).to_string(index=False))
        print(f"\n=== {feed} 全体: 未収載停留所の数・車なし率の加重平均")
        vs = s[s.feed == feed]
        print("停留所", len(vs), "未収載", int((~vs.mapped).sum()))
        vt = t[t.feed == feed]
        print("車なし率(停留所のある tract)", round(vt.hh_no_vehicle.sum() / vt.hh_total.sum(), 3), "\n")
    print("\n=== 比較: 都市ごとの車なし率")
    for f in sorted(t.feed.unique()):
        g = t[t.feed == f]
        print(f, "車なし率", round(g.hh_no_vehicle.sum() / g.hh_total.sum(), 3), "停留所", int(g.stops.sum()))
    print("\n=== Pahto: tract 別")
    p = t[t.feed == "pahto_yakama"]
    print(p[["GEOID", "stops", "mapped", "hh_total", "hh_no_vehicle", "noveh_share", "svi_overall", "ur_class"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
