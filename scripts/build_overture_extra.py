"""10/15 夜の棚卸し(docs/overture_columns.md)で残った未使用列の tract 集計。受付の許可後に実行する。

道路 H6: tertiary 以下でも、制限速度が高い区間(≥ 45 mph)は機能上の collector で、参照の S1200 に入りうる。
         class = unknown(配布の roads では除かれた)のうち、名前が幹線の型の区間も同じ理由で数える。
事業所 P2: CBP は従業員のいる事業所だけを数える。家で営む業種(住宅サービス・不動産・美容など)の places は
         CBP に対応が無く、分子だけを膨らませる。閉業(permanently_closed)・チェーン(brand あり)も数える。
出力: data/processed/ov_extra_<region>.parquet
使い方: DUCKDB_MEMORY_LIMIT=2GB DUCKDB_THREADS=4 python scripts/build_overture_extra.py [region ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref, strata  # noqa: E402
from scripts.build_road_named import PAT  # noqa: E402
from scripts.build_tiger_proxy import m  # noqa: E402

OUT = ROOT / "data" / "processed"
HOME_CATS = ("home_service", "real_estate_service", "personal_or_beauty_service", "professional_service",
             "construction_service", "event_or_party_service")


def roads(con, region: str):
    hwy = "|".join(f"({p.removeprefix('(?i)')})" for p in PAT.values())
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE rd AS
        SELECT {m('geometry')} AS g, class,
               try_cast(speed_limits[1].max_speed.value AS INTEGER) AS sp, speed_limits[1].max_speed.unit AS unit,
               regexp_matches(coalesce(names.primary, ''), '(?i){hwy}') AS hwyname
        FROM {ref(region, 'overture-roads-unfiltered')}
        WHERE class IN ('tertiary', 'residential', 'unclassified', 'unknown')
    """)
    con.sql("""CREATE OR REPLACE TEMP TABLE rd AS
               SELECT * FROM rd WHERE (class <> 'unknown' AND (CASE WHEN unit = 'km/h' THEN sp * 0.621 ELSE sp END) >= 45)
                                   OR (class = 'unknown' AND hwyname)""")
    return con.sql("""
        SELECT tr.GEOID,
          sum(km) FILTER (WHERE class = 'tertiary') AS sp45_ter_km,
          sum(km) FILTER (WHERE class IN ('residential', 'unclassified')) AS sp45_loc_km,
          sum(km) FILTER (WHERE class = 'unknown') AS unk_hwy_km
        FROM (SELECT tr.GEOID, rd.class, ST_Length(ST_Intersection(rd.g, tr.g)) / 1000 AS km
              FROM rd JOIN tr ON ST_Intersects(rd.g, tr.g)) tr
        GROUP BY 1
    """).df()


def places(con, region: str):
    hc = ", ".join(f"'{c}'" for c in HOME_CATS)
    return con.sql(f"""
        WITH p AS (SELECT geometry AS g, basic_category AS bc, operating_status AS os, brand IS NOT NULL AS br,
                          websites IS NOT NULL OR phones IS NOT NULL AS contact
                   FROM {ref(region, 'overture-pois')})
        SELECT tr.GEOID,
          count(*) FILTER (WHERE bc IN ({hc})) AS pl_home_n,
          count(*) FILTER (WHERE os = 'permanently_closed') AS pl_closed_n,
          count(*) FILTER (WHERE br) AS pl_brand_n,
          count(*) FILTER (WHERE NOT contact) AS pl_nocontact_n
        FROM p JOIN tr ON ST_Within(p.g, tr.g) GROUP BY 1
    """).df()


def build(con, region: str) -> None:
    t0 = time.time()
    con.sql(f"CREATE OR REPLACE TEMP TABLE tr AS SELECT GEOID, {m('geometry')} AS g FROM {strata(region, 'census-tracts')}")
    r = roads(con, region)
    # places は点。tract も CRS84 のまま比べる(build_poi_features.py と同じ)
    con.sql(f"CREATE OR REPLACE TEMP TABLE tr AS SELECT GEOID, geometry AS g FROM {strata(region, 'census-tracts')}")
    p = places(con, region)
    df = r.merge(p, on="GEOID", how="outer")
    df.to_parquet(OUT / f"ov_extra_{region}.parquet", index=False)
    s = df.drop(columns="GEOID").sum()
    print(f"[{region}] rows={len(df)} " + " ".join(f"{k}={v:.0f}" for k, v in s.items()) + f" {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect()
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
