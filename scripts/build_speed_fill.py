"""H6(速い tertiary)の追跡用: tertiary の制限速度の埋まり具合を地域・tract ごとに数える。受付の許可後に実行する。

t_sp45 は「制限速度 ≥ 45 mph の tertiary」を数えるが、制限速度が入っていない区間は 0 と扱っている。
TX・CA・AZ の sp45 割合が低いのが「遅い」からか「書かれていない」からかを、ここで分ける。
出力: data/processed/ov_speed_<region>.parquet(ter_km_all / ter_km_sp / ter_km_sp45)
使い方: DUCKDB_MEMORY_LIMIT=2GB DUCKDB_THREADS=4 python scripts/build_speed_fill.py [region ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref, strata  # noqa: E402
from scripts.build_tiger_proxy import m  # noqa: E402

OUT = ROOT / "data" / "processed"


def build(con, region: str) -> None:
    t0 = time.time()
    con.sql(f"CREATE OR REPLACE TEMP TABLE tr AS SELECT GEOID, {m('geometry')} AS g FROM {strata(region, 'census-tracts')}")
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE rd AS
        SELECT {m('geometry')} AS g,
               CASE WHEN speed_limits[1].max_speed.unit = 'km/h'
                    THEN try_cast(speed_limits[1].max_speed.value AS INTEGER) * 0.621
                    ELSE try_cast(speed_limits[1].max_speed.value AS INTEGER) END AS mph
        FROM {ref(region, 'overture-roads-unfiltered')}
        WHERE class = 'tertiary'
    """)
    df = con.sql("""
        SELECT GEOID, sum(km) AS ter_km_all,
               coalesce(sum(km) FILTER (WHERE mph IS NOT NULL), 0) AS ter_km_sp,
               coalesce(sum(km) FILTER (WHERE mph >= 45), 0) AS ter_km_sp45
        FROM (SELECT tr.GEOID, rd.mph, ST_Length(ST_Intersection(rd.g, tr.g)) / 1000 AS km
              FROM rd JOIN tr ON ST_Intersects(rd.g, tr.g))
        GROUP BY 1
    """).df()
    df.to_parquet(OUT / f"ov_speed_{region}.parquet", index=False)
    a, s, f = df["ter_km_all"].sum(), df["ter_km_sp"].sum(), df["ter_km_sp45"].sum()
    print(f"[{region}] tracts={len(df)} ter_km={a:.0f} 埋まり={s / a:.1%} ≥45/埋まり={f / max(s, 1e-9):.1%} "
          f"{time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect()
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
