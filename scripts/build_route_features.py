"""Overture 道路の路線情報(routes.network)から、tract ごとの路線種別別の延長を集計する。

狙い: 採点の道路成分は TIGER S1100(インターステート)+ S1200(国道・州道)に対する
Overture の幹線クラス(motorway/trunk/primary/secondary)延長の比。TIGER は使えないので、
Overture 自身の路線番号つき区間の延長を基準量の代わりにする。

network の分類:
  I        : US:I(インターステート本線)
  US       : US:US(国道本線)
  ST       : US:<州>(州道本線)
  SUB      : US:I|US|<州>:<Business|Truck|Bypass|Loop|Spur|Alternate|...>(付随路線, FM なども含む)
  COUNTY   : US:<州>:<郡名>(郡道) — 判定は「3 階層で 3 番目が既知の付随種別でない」
区間に複数の routes があれば、上の順で最上位の 1 種別に数える(重複計上しない)。

出力: data/processed/routes_<region>.parquet(各種別の全延長と、そのうち幹線クラスの延長)
使い方: python scripts/build_route_features.py [region ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref, strata  # noqa: E402

OUT = ROOT / "data" / "processed"
SUB = "Business|Truck|Bypass|Loop|Spur|Alternate|Alt|Connector|Historic|Scenic|FM|RM|PR|Park|Toll|Frontage|Beltway|Rec|Express"


def to_m(geom: str) -> str:
    return f"ST_Transform({geom}, 'EPSG:4326', 'EPSG:5070', always_xy := true)"


def build(con, region: str) -> None:
    t0 = time.time()
    con.sql(f"CREATE OR REPLACE TEMP TABLE tracts AS SELECT GEOID, geometry AS geom FROM {strata(region, 'census-tracts')}")
    df = con.sql(f"""
        WITH r AS (
            SELECT geometry AS g, class,
                   list_transform(coalesce(routes, []), x -> x.network) AS nets
            FROM {ref(region, 'overture-roads')}
        ), k AS (
            SELECT g, class,
                CASE
                  WHEN list_contains(nets, 'US:I') THEN 'I'
                  WHEN list_contains(nets, 'US:US') THEN 'US'
                  WHEN len(list_filter(nets, n -> regexp_full_match(n, 'US:[A-Z]{{2}}'))) > 0 THEN 'ST'
                  WHEN len(list_filter(nets, n -> regexp_full_match(n, 'US:(I|US|[A-Z]{{2}}):({SUB}).*'))) > 0 THEN 'SUB'
                  WHEN len(list_filter(nets, n -> regexp_full_match(n, 'US:[A-Z]{{2}}:.+'))) > 0 THEN 'COUNTY'
                  ELSE 'NONE' END AS kind
            FROM r
        ), j AS (
            SELECT t.GEOID, k.kind, k.class IN ('motorway','trunk','primary','secondary') AS hw,
                   ST_Length({to_m('ST_Intersection(k.g, t.geom)')}) AS len_m
            FROM k JOIN tracts t ON ST_Intersects(k.g, t.geom)
        )
        SELECT GEOID,
          {", ".join(f"sum(len_m) FILTER (WHERE kind = '{c}') / 1000 AS rt_{c.lower()}_km, "
                     f"sum(len_m) FILTER (WHERE kind = '{c}' AND hw) / 1000 AS rt_{c.lower()}_hw_km"
                     for c in ("I", "US", "ST", "SUB", "COUNTY", "NONE"))}
        FROM j GROUP BY 1
    """).df()
    df.to_parquet(OUT / f"routes_{region}.parquet", index=False)
    print(f"[{region}] rows={len(df)} {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect()
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
