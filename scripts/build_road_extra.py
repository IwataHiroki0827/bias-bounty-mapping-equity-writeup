"""道路推定の取りこぼし候補: 路線番号(routes)の付いていない motorway / trunk の延長を tract ごとに集計する。

TIGER の S1100(primary)は出入り制限のある幹線で、Overture ではほぼ motorway / trunk になる。
番号つき路線だけで TIGER を近似すると、routes の関係が欠けた区間(ランプ以外の本線)を取りこぼす。
出力: data/processed/road_extra_<region>.parquet
  mt_nonum_in_km    : tract 内の、番号なし motorway/trunk の延長(*_link は除く)
  mt_nonum_ring15_km: 外側 15m 帯の同延長(境界の二重計上)
使い方: python scripts/build_road_extra.py [region ...]
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


def build(con, region: str) -> None:
    t0 = time.time()
    con.sql(f"CREATE OR REPLACE TEMP TABLE tr AS SELECT GEOID, {m('geometry')} AS g FROM {strata(region, 'census-tracts')}")
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE seg AS
        SELECT {m('geometry')} AS g
        FROM {ref(region, 'overture-roads')}
        WHERE class IN ('motorway', 'trunk')
          AND coalesce(subclass, '') <> 'link'
          AND len(list_filter(coalesce(routes, []), x -> regexp_full_match(coalesce(x.network, ''), '{NUM}'))) = 0
    """)
    inside = con.sql("""
        SELECT tr.GEOID, sum(ST_Length(ST_Intersection(seg.g, tr.g))) / 1000 AS mt_nonum_in_km
        FROM seg JOIN tr ON ST_Intersects(seg.g, tr.g) GROUP BY 1
    """).df().set_index("GEOID")
    con.sql("CREATE OR REPLACE TEMP TABLE ring AS SELECT GEOID, ST_Difference(ST_Buffer(g, 15), g) AS g FROM tr")
    ring = con.sql("""
        SELECT ring.GEOID, sum(ST_Length(ST_Intersection(seg.g, ring.g))) / 1000 AS mt_nonum_ring15_km
        FROM seg JOIN ring ON ST_Intersects(seg.g, ring.g) GROUP BY 1
    """).df().set_index("GEOID")
    df = inside.join(ring, how="outer").reset_index()
    df.to_parquet(OUT / f"road_extra_{region}.parquet", index=False)
    print(f"[{region}] rows={len(df)} km_in={df['mt_nonum_in_km'].sum():.0f} {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect(threads=4)
    con.sql("SET memory_limit='3GB'")  # 共有マシンの資源規則(受付への申告値)。超える分は DuckDB がディスクへ逃がす
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
