"""建物成分(Overture 棟 / MS 棟)の推定用に、Overture buildings を供給元別の棟数・面積と、棟の大きさの区分で数える。

機構(Overture 公式 buildings ガイド): 統合の優先順は OSM → Esri → Google 高 → MS で、MS の棟は上位と交差しないものだけが入る。
上位(OSM 等)が大きな1ポリゴンで複数の建物を描いた tract では、MS の複数棟がその1ポリゴンに置き換わり、Overture 棟 < MS 棟になる。
→ 上位由来の棟の平均面積が、同じ tract の MS 由来の棟より大きいほど、建物ギャップが大きいと予測する。

出力: data/processed/bldg_sources_<region>.parquet(地域ごとに上書き。溜まらない)
使い方: python scripts/build_bldg_sources.py [region ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.build_features import to_m  # noqa: E402
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref, strata  # noqa: E402

OUT = ROOT / "data" / "processed"


def build(con, region: str) -> None:
    t0 = time.time()
    df = con.sql(f"""
        WITH b AS (
            SELECT ST_PointOnSurface(geometry) AS pt,
                   sources[1].dataset = 'Microsoft ML Buildings' AS is_ms,
                   ST_Area({to_m('geometry')}) AS a
            FROM {ref(region, 'overture-buildings')}
        ), t AS (SELECT GEOID, geometry AS g FROM {strata(region, 'census-tracts')})
        SELECT t.GEOID,
               sum(a) FILTER (WHERE is_ms) AS bs_ms_area,
               sum(a) FILTER (WHERE NOT is_ms) AS bs_up_area,
               count(*) FILTER (WHERE NOT is_ms AND a >= 400) AS bs_up_big400_n,
               count(*) FILTER (WHERE NOT is_ms AND a >= 1500) AS bs_up_big1500_n,
               count(*) FILTER (WHERE is_ms AND a < 60) AS bs_ms_small_n,
               count(*) FILTER (WHERE NOT is_ms AND a < 60) AS bs_up_small_n,
               median(a) FILTER (WHERE NOT is_ms) AS bs_up_med_area,
               median(a) FILTER (WHERE is_ms) AS bs_ms_med_area
        FROM b JOIN t ON ST_Within(b.pt, t.g) GROUP BY 1
    """).df()
    df.to_parquet(OUT / f"bldg_sources_{region}.parquet", index=False)
    print(f"[{region}] tracts={len(df)} {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect(threads=4)
    con.sql("SET memory_limit = '2GB'")
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
