"""道路の取りこぼし仮説 H4(Fable 10/15 の案①): 取り込み時代の番号なし幹線。tract ごとに出す。

機構: TIGER S1200 は番号の無い連絡道路も含む。OSM の 2007–08 TIGER 取り込みで入り、その後だれも編集していない
     区間(Overture の sources[1].update_time < 2012)は、今も幹線クラスに残り、参照でも S1200 のまま
     → 番号つき近似が取りこぼす分(k=1.4 で水準だけ吸収している約4割)の候補。
集計: 幹線4クラス(motorway/trunk/primary/secondary、tg_ov_hw_km と同じ)を tract で切り取った延長を、
     番号あり/なし × 取り込み時代(更新が 2012 年より前)/それ以降 の4区分で出す。
出力: data/processed/road_age_<region>.parquet(age_num_old_km, age_num_new_km, age_unnum_old_km, age_unnum_new_km)
使い方: DUCKDB_MEMORY_LIMIT=2GB DUCKDB_THREADS=4 python scripts/build_road_age.py [region ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref, strata  # noqa: E402
from scripts.build_tiger_proxy import NUM, m  # noqa: E402

OUT = ROOT / "data" / "processed"
CUT = "2012-01-01"


def build(con, region: str) -> None:
    t0 = time.time()
    con.sql(f"CREATE OR REPLACE TEMP TABLE tr AS SELECT GEOID, {m('geometry')} AS g FROM {strata(region, 'census-tracts')}")
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE hw AS
        SELECT {m('geometry')} AS g,
               len(list_filter(coalesce(routes, []), x -> regexp_full_match(coalesce(x.network, ''), '{NUM}'))) > 0 AS numbered,
               coalesce(try_cast(sources[1].update_time AS TIMESTAMP) < TIMESTAMP '{CUT}', false) AS old
        FROM {ref(region, 'overture-roads')}
        WHERE class IN ('motorway', 'trunk', 'primary', 'secondary')
    """)
    df = con.sql("""
        SELECT GEOID,
               sum(CASE WHEN numbered AND old THEN km END) AS age_num_old_km,
               sum(CASE WHEN numbered AND NOT old THEN km END) AS age_num_new_km,
               sum(CASE WHEN NOT numbered AND old THEN km END) AS age_unnum_old_km,
               sum(CASE WHEN NOT numbered AND NOT old THEN km END) AS age_unnum_new_km
        FROM (SELECT tr.GEOID, hw.numbered, hw.old, ST_Length(ST_Intersection(hw.g, tr.g)) / 1000 AS km
              FROM hw JOIN tr ON ST_Intersects(hw.g, tr.g)) x
        GROUP BY 1
    """).df()
    df.to_parquet(OUT / f"road_age_{region}.parquet", index=False)
    s = df.drop(columns="GEOID").sum()
    print(f"[{region}] rows={len(df)} " + " ".join(f"{k}={v:.0f}" for k, v in s.items()) + f" {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect()
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
