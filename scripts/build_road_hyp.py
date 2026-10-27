"""道路の取りこぼし仮説 H1 / H3 の集計(docs/road_hypotheses.md)。tract ごとに出す。

H1(分離車線): 番号の無い motorway/trunk 本線のうち、番号つき区間から 60m 以内を走る延長
               = 上下線の片側にだけ routes が付いている区間の候補
H3(ランプ):   motorway/trunk の link(subclass = 'link')の延長 = 分子(Overture 幹線延長)に入っている可能性のある分
出力: data/processed/road_hyp_<region>.parquet(h1_pair_km, h3_link_km)
使い方: DUCKDB_MEMORY_LIMIT=3GB DUCKDB_THREADS=4 python scripts/build_road_hyp.py [region ...]
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
PAIR_M = 60


def build(con, region: str) -> None:
    t0 = time.time()
    con.sql(f"CREATE OR REPLACE TEMP TABLE tr AS SELECT GEOID, {m('geometry')} AS g FROM {strata(region, 'census-tracts')}")
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE mt AS
        SELECT {m('geometry')} AS g, coalesce(subclass, '') = 'link' AS link,
               len(list_filter(coalesce(routes, []), x -> regexp_full_match(coalesce(x.network, ''), '{NUM}'))) > 0 AS numbered
        FROM {ref(region, 'overture-roads')}
        WHERE class IN ('motorway', 'trunk')
    """)
    # H1: 番号なし本線のうち、番号つき本線から PAIR_M 以内にあるもの(区間単位で判定)
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE pair AS
        SELECT DISTINCT a.g
        FROM mt a JOIN mt b ON NOT a.link AND NOT b.link AND NOT a.numbered AND b.numbered
                           AND ST_DWithin(a.g, b.g, {PAIR_M})
    """)
    h1 = con.sql("""
        SELECT tr.GEOID, sum(ST_Length(ST_Intersection(pair.g, tr.g))) / 1000 AS h1_pair_km
        FROM pair JOIN tr ON ST_Intersects(pair.g, tr.g) GROUP BY 1
    """).df().set_index("GEOID")
    h3 = con.sql("""
        SELECT tr.GEOID, sum(ST_Length(ST_Intersection(mt.g, tr.g))) / 1000 AS h3_link_km
        FROM mt JOIN tr ON mt.link AND ST_Intersects(mt.g, tr.g) GROUP BY 1
    """).df().set_index("GEOID")
    df = h1.join(h3, how="outer").reset_index()
    df.to_parquet(OUT / f"road_hyp_{region}.parquet", index=False)
    print(f"[{region}] rows={len(df)} h1_km={df['h1_pair_km'].sum():.0f} h3_km={df['h3_link_km'].sum():.0f} "
          f"{time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect()
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
