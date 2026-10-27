"""施設成分の推定用に、Overture places から消防・救急・学校の手がかりを tract ごとに数える。

採点は categories.primary だけで施設種別を判定する。名前が消防署なのにカテゴリが別の施設
(fire_protection_service, 役所, 警察 など)がある tract は、実在の消防署があるのに採点では
0 件と数えられ、消防ギャップが 1 になりやすい(スレッド 34925 の観察)。名前の判定式は同スレッドのもの。

出力: data/processed/poi_<region>.parquet
使い方: python scripts/build_poi_features.py [region ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref, strata  # noqa: E402

OUT = ROOT / "data" / "processed"
FIRE_NAME = (r"\bfire\s*(station|dept|department|protection district|district|authority|rescue|company|co\b|house|hall)"
             r"|\bvfd\b|\bfpd\b|\bcal ?fire\b|volunteer fire|fire\s*/\s*ems|fire & ems|fire and ems")
FIRE_NOT = r"auxil|thrift|supply|equipment|extinguish|sprinkler|safety|alarm|training|museum|store|shop|academy|insurance"
EMS_NAME = r"\bems\b|ambulance|emergency medical|rescue squad"
SCHOOL_CATS = ("elementary_school", "middle_school", "high_school", "school", "private_school", "public_school")


def build(con, region: str) -> None:
    t0 = time.time()
    sc = ", ".join(f"'{c}'" for c in SCHOOL_CATS)
    df = con.sql(f"""
        WITH p AS (
            SELECT geometry AS g, categories.primary AS cat, lower(coalesce(names.primary, '')) AS nm, confidence
            FROM {ref(region, 'overture-pois')}
        ), t AS (SELECT GEOID, geometry AS g FROM {strata(region, 'census-tracts')})
        SELECT t.GEOID,
          count(*) FILTER (WHERE cat = 'fire_department') AS fire_cat_n,
          count(*) FILTER (WHERE cat IS DISTINCT FROM 'fire_department'
                           AND regexp_matches(nm, '{FIRE_NAME}') AND NOT regexp_matches(nm, '{FIRE_NOT}')) AS fire_misfiled_n,
          count(*) FILTER (WHERE cat = 'fire_protection_service') AS fire_prot_n,
          count(*) FILTER (WHERE cat = 'ambulance_and_ems_services') AS ems_cat_n,
          count(*) FILTER (WHERE cat IS DISTINCT FROM 'ambulance_and_ems_services' AND regexp_matches(nm, '{EMS_NAME}')) AS ems_misfiled_n,
          count(*) FILTER (WHERE cat IN ({sc})) AS school_cat_n,
          count(*) FILTER (WHERE cat NOT IN ({sc}) AND regexp_matches(nm, '\\b(elementary|middle|high|junior high|intermediate) school\\b')) AS school_misfiled_n,
          count(*) FILTER (WHERE confidence < 0.5) AS poi_lowconf_n,
          count(*) AS poi_all_n
        FROM p JOIN t ON ST_Within(p.g, t.g) GROUP BY 1
    """).df()
    df.to_parquet(OUT / f"poi_{region}.parquet", index=False)
    print(f"[{region}] rows={len(df)} fire_misfiled tracts={int((df.fire_misfiled_n > 0).sum())} {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect()
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
