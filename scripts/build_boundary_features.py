"""境界道路の仮説のための特徴: tract を d メートル膨らませた範囲に入る Overture 幹線の延長。

仮説: tract 境界は幹線に沿って引かれることが多い。基準側の道路は境界線上に乗り、切り取ると隣り合う
両方の tract に延長が入る。Overture の同じ道路は数メートルずれて片側にしか入らないので、反対側では
「基準にはあるが Overture に無い」状態になる。よって tract の基準延長は、膨らませた tract 内の
Overture 幹線延長 hw_buf_<d> で近似でき、hw_in / hw_buf_<d> が道路成分の比の代わりになる。

出力: data/processed/boundary_<region>.parquet
使い方: python scripts/build_boundary_features.py [region ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref, strata  # noqa: E402

OUT = ROOT / "data" / "processed"
DISTS = (10, 25, 50, 100)


def m(g: str) -> str:
    return f"ST_Transform({g}, 'EPSG:4326', 'EPSG:5070', always_xy := true)"


def build(con, region: str) -> None:
    t0 = time.time()
    con.sql(f"CREATE OR REPLACE TEMP TABLE tr AS SELECT GEOID, {m('geometry')} AS g FROM {strata(region, 'census-tracts')}")
    con.sql(f"""CREATE OR REPLACE TEMP TABLE hw AS SELECT {m('geometry')} AS g FROM {ref(region, 'overture-roads')}
                WHERE class IN ('motorway','trunk','primary','secondary')""")
    parts = []
    for d in (0,) + DISTS:
        geom = "tr.g" if d == 0 else f"ST_Buffer(tr.g, {d})"
        name = "hw_in_km" if d == 0 else f"hw_buf{d}_km"
        con.sql(f"CREATE OR REPLACE TEMP TABLE trb AS SELECT GEOID, {geom} AS g FROM tr")
        parts.append(con.sql(f"""SELECT trb.GEOID, sum(ST_Length(ST_Intersection(hw.g, trb.g))) / 1000 AS {name}
                                 FROM hw JOIN trb ON ST_Intersects(hw.g, trb.g) GROUP BY 1""").df().set_index("GEOID"))
    df = parts[0].join(parts[1:], how="outer").reset_index()
    df.to_parquet(OUT / f"boundary_{region}.parquet", index=False)
    print(f"[{region}] rows={len(df)} {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect()
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
