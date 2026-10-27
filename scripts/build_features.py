"""Overture・ACS を tract ごとに集計し、data/processed/features_<region>.parquet に保存する。

リモート(Source Cooperative)のまま DuckDB で集計し、ローカルには集計結果だけを置く。
割り当て規則:
  - 建物・POI: 代表点(ST_PointOnSurface / 点そのもの)が入る tract
  - 道路: tract ポリゴンで切り取った長さ(EPSG:5070, always_xy)

使い方: python scripts/build_features.py [region ...]   # 省略時は全地域
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import BASE, REGIONS, connect, ref, strata  # noqa: E402

OUT = ROOT / "data" / "processed"
HIGHWAY = ("motorway", "trunk", "primary", "secondary")
SCHOOLS = ("elementary_school", "middle_school", "high_school", "school", "private_school", "public_school")


def to_m(geom: str) -> str:
    return f"ST_Transform({geom}, 'EPSG:4326', 'EPSG:5070', always_xy := true)"


def build(con, region: str) -> None:
    t0 = time.time()
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE tracts AS
        SELECT GEOID, geometry AS geom FROM {strata(region, 'census-tracts')}
    """)
    n_tracts = con.sql("SELECT count(*) FROM tracts").fetchone()[0]

    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE f_bldg AS
        WITH b AS (
            SELECT ST_PointOnSurface(geometry) AS pt,
                   sources[1].dataset AS ds,
                   names.primary IS NOT NULL AS has_name,
                   height IS NOT NULL AS has_height,
                   ST_Area({to_m('geometry')}) AS area_m2
            FROM {ref(region, 'overture-buildings')}
        )
        SELECT t.GEOID,
               count(*) AS bldg_n,
               count(*) FILTER (WHERE ds = 'Microsoft ML Buildings') AS bldg_ms_n,
               count(*) FILTER (WHERE ds = 'OpenStreetMap') AS bldg_osm_n,
               count(*) FILTER (WHERE ds NOT IN ('Microsoft ML Buildings', 'OpenStreetMap')) AS bldg_other_n,
               count(*) FILTER (WHERE has_name) AS bldg_named_n,
               count(*) FILTER (WHERE has_height) AS bldg_height_n,
               sum(area_m2) AS bldg_area_m2
        FROM b JOIN tracts t ON ST_Within(b.pt, t.geom)
        GROUP BY 1
    """)
    t1 = time.time()

    hw = ", ".join(f"'{c}'" for c in HIGHWAY)
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE f_road AS
        WITH r AS (
            SELECT geometry AS g, class, names.primary IS NULL AS unnamed
            FROM {ref(region, 'overture-roads')}
        ), j AS (
            SELECT t.GEOID, r.class, r.unnamed,
                   ST_Length({to_m('ST_Intersection(r.g, t.geom)')}) AS len_m
            FROM r JOIN tracts t ON ST_Intersects(r.g, t.geom)
        )
        SELECT GEOID,
               sum(len_m) FILTER (WHERE class IN ({hw})) / 1000 AS road_hw_km,
               sum(len_m) FILTER (WHERE class = 'motorway') / 1000 AS road_motorway_km,
               sum(len_m) FILTER (WHERE class = 'trunk') / 1000 AS road_trunk_km,
               sum(len_m) FILTER (WHERE class = 'primary') / 1000 AS road_primary_km,
               sum(len_m) FILTER (WHERE class = 'secondary') / 1000 AS road_secondary_km,
               sum(len_m) FILTER (WHERE class = 'tertiary') / 1000 AS road_tertiary_km,
               sum(len_m) / 1000 AS road_all_km,
               sum(len_m) FILTER (WHERE unnamed) / 1000 AS road_unnamed_km
        FROM j GROUP BY 1
    """)
    t2 = time.time()

    sc = ", ".join(f"'{c}'" for c in SCHOOLS)
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE f_poi AS
        SELECT t.GEOID,
               count(*) AS poi_n,
               count(*) FILTER (WHERE categories.primary = 'fire_department') AS poi_fire_n,
               count(*) FILTER (WHERE categories.primary = 'ambulance_and_ems_services') AS poi_ems_n,
               count(*) FILTER (WHERE categories.primary IN ({sc})) AS poi_school_n,
               count(*) FILTER (WHERE categories.primary = 'hospital') AS poi_hospital_n,
               avg(confidence) AS poi_conf_mean
        FROM {ref(region, 'overture-pois')} p JOIN tracts t ON ST_Within(p.geometry, t.geom)
        GROUP BY 1
    """)
    t3 = time.time()

    df = con.sql(f"""
        SELECT s.GEOID, '{region}' AS region, a.* EXCLUDE (GEOID, bbox),
               b.* EXCLUDE (GEOID), r.* EXCLUDE (GEOID), p.* EXCLUDE (GEOID)
        FROM read_csv('{BASE}/reference/{region}/{region}-sample-submission.csv',
                      types={{'GEOID': 'VARCHAR'}}) s
        LEFT JOIN (SELECT * EXCLUDE (geometry) FROM {ref(region, 'census-acs-housing')}) a USING (GEOID)
        LEFT JOIN f_bldg b USING (GEOID)
        LEFT JOIN f_road r USING (GEOID)
        LEFT JOIN f_poi p USING (GEOID)
    """).df()
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT / f"features_{region}.parquet", index=False)
    print(f"[{region}] tracts={n_tracts} rows={len(df)} "
          f"bldg={t1 - t0:.0f}s road={t2 - t1:.0f}s poi={t3 - t2:.0f}s total={time.time() - t0:.0f}s", flush=True)


def check_length(con) -> None:
    """座標順の罠の検算: 経度1度ぶんの東西線(北緯35度)は約91.3km。"""
    line = to_m("ST_GeomFromText('LINESTRING(-96 35, -95 35)')")
    km = con.sql(f"SELECT ST_Length({line}) / 1000").fetchone()[0]
    print(f"検算: 北緯35度の経度1度 = {km:.2f} km(期待 91.29 km 前後)")
    if not (88 < km < 95):
        raise SystemExit("長さの検算に失敗。CRS の軸順を確認")


def main() -> None:
    regions = sys.argv[1:] or REGIONS
    con = connect()
    check_length(con)
    for region in regions:
        build(con, region)


if __name__ == "__main__":
    main()
