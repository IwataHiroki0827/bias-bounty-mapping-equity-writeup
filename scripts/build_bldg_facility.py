"""F1(10/18 Fable): Overture buildings の class / subtype / names で、消防署・学校・EMS の建物を tract ごとに数える。受付の許可後に実行する。

機構: 参照(撤去済み)の消防署・学校は実在の施設。Overture places に無くても、OSM 由来の建物ポリゴンが
building=fire_station / school や「… Fire Station」の名前を持っていれば、buildings の class・names に載る。
places から作った既存の特徴とは供給元が重ならない。
出力: data/processed/bldg_facility_<region>.parquet(地域ごとに上書き)
使い方: python scripts/build_bldg_facility.py [region ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.build_poi_features import EMS_NAME, FIRE_NAME, FIRE_NOT  # noqa: E402
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref, strata  # noqa: E402

OUT = ROOT / "data" / "processed"
SCHOOL_NAME = r"\b(elementary|middle|high|junior high|intermediate|primary|charter|isd)\b.*\bschool\b|\bschool\b|\bacademy\b"
SCHOOL_CLASS = ("school", "kindergarten")


def build(con, region: str) -> None:
    t0 = time.time()
    sc = ", ".join(f"'{c}'" for c in SCHOOL_CLASS)
    df = con.sql(f"""
        WITH b AS (
            SELECT ST_PointOnSurface(geometry) AS pt, class AS cl, subtype AS st,
                   lower(coalesce(names.primary, '')) AS nm
            FROM {ref(region, 'overture-buildings')}
            WHERE class IN ('fire_station', {sc}) OR subtype IN ('civic', 'education') OR names.primary IS NOT NULL
        ), f AS (
            SELECT pt,
                   cl = 'fire_station' OR (regexp_matches(nm, '{FIRE_NAME}') AND NOT regexp_matches(nm, '{FIRE_NOT}')) AS is_fire,
                   cl IN ({sc}) OR (regexp_matches(nm, '{SCHOOL_NAME}') AND NOT regexp_matches(nm, 'driving|beauty|dance|martial|swim')) AS is_school,
                   regexp_matches(nm, '{EMS_NAME}') AS is_ems,
                   st = 'education' AS is_edu
            FROM b
        ), t AS (SELECT GEOID, geometry AS g FROM {strata(region, 'census-tracts')})
        SELECT t.GEOID,
               count(*) FILTER (WHERE is_fire) AS bf_fire_n,
               count(*) FILTER (WHERE is_school) AS bf_school_n,
               count(*) FILTER (WHERE is_ems) AS bf_ems_n,
               count(*) FILTER (WHERE is_edu) AS bf_edu_n
        FROM f JOIN t ON ST_Within(f.pt, t.g)
        WHERE is_fire OR is_school OR is_ems OR is_edu
        GROUP BY 1
    """).df()
    df.to_parquet(OUT / f"bldg_facility_{region}.parquet", index=False)
    s = df.drop(columns="GEOID").sum()
    print(f"[{region}] tracts={len(df)} " + " ".join(f"{k}={v:.0f}" for k, v in s.items()) + f" {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect(threads=4)
    con.sql("SET memory_limit = '2GB'")
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
