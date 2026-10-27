"""道路の取りこぼし仮説 H5(10/15): 名前が「幹線の呼び名」なのに、Overture では幹線クラスでない区間。tract ごとに出す。

機構: 参照(TIGER S1100+S1200)は、州道・郡道・FM 道などの名前つき路線を含む。Overture がそれを tertiary 以下に
     分類していると、参照には数えられて Overture の幹線には入らない → 道路ギャップの源。番号つき路線(routes)の近似は、
     routes が付いていない区間を取りこぼす(t_ter05 の当たり +0.046 は tertiary の一部が S1200 であることと整合)。
     名前の型で、tertiary 以下のうち参照に入りそうな区間だけを拾う。
集計: names.primary の型 × クラス(幹線4 / tertiary / residential・unclassified)の延長(tract で切り取り)。
     型: cty = County Road / CR / Co Rd、fm = FM / RM / Farm(Ranch) to Market、st = State Hwy / SH / Highway / Hwy / US / Interstate / I-、
     その他の名前つき・名前なしは数えない。参考に、クラス別の sources[1].dataset の延長も地域の合計で表示する。
出力: data/processed/road_named_<region>.parquet(nm_<型>_<クラス>_km)
使い方: DUCKDB_MEMORY_LIMIT=2GB DUCKDB_THREADS=4 python scripts/build_road_named.py [region ...]
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
PAT = {
    "cty": r"(?i)^(county (road|rd|highway|hwy)|co\.? ?(rd|road)|cr)\b",
    "fm": r"(?i)^(fm|rm|farm[- ]to[- ]market|ranch[- ]to[- ]market|ranch road)\b",
    "st": r"(?i)(\bstate (highway|hwy|route|road)\b|^(sh|hwy|highway|us|u\.s\.|interstate|i)[- ]?\d|\bhighway\b|\bhwy\b)",
}


def build(con, region: str) -> None:
    t0 = time.time()
    con.sql(f"CREATE OR REPLACE TEMP TABLE tr AS SELECT GEOID, {m('geometry')} AS g FROM {strata(region, 'census-tracts')}")
    kind = " ".join(f"WHEN regexp_matches(nm, '{p}') THEN '{k}'" for k, p in PAT.items())
    con.sql(f"""
        CREATE OR REPLACE TEMP TABLE rd AS
        SELECT {m('geometry')} AS g,
               CASE WHEN class IN ('motorway','trunk','primary','secondary') THEN 'hw'
                    WHEN class = 'tertiary' THEN 'ter' ELSE 'loc' END AS cl,
               CASE {kind} ELSE NULL END AS kind,
               coalesce(sources[1].dataset, '') AS ds
        FROM (SELECT *, coalesce(names.primary, '') AS nm FROM {ref(region, 'overture-roads')})
    """)
    print(f"[{region}] 供給元(全クラス km 合計は下の表):", flush=True)
    print(con.sql("""SELECT cl, ds, round(sum(ST_Length(g)) / 1000) AS km FROM rd GROUP BY 1, 2 ORDER BY 1, 3 DESC""").df()
          .to_string(index=False), flush=True)
    cols = ", ".join(f"sum(km) FILTER (WHERE kind = '{k}' AND cl = '{c}') AS nm_{k}_{c}_km"
                     for k in PAT for c in ("hw", "ter", "loc"))
    df = con.sql(f"""
        SELECT GEOID, {cols}
        FROM (SELECT tr.GEOID, rd.kind, rd.cl, ST_Length(ST_Intersection(rd.g, tr.g)) / 1000 AS km
              FROM rd JOIN tr ON rd.kind IS NOT NULL AND ST_Intersects(rd.g, tr.g)) x
        GROUP BY 1
    """).df()
    df.to_parquet(OUT / f"road_named_{region}.parquet", index=False)
    s = df.drop(columns="GEOID").sum()
    print(f"[{region}] rows={len(df)} " + " ".join(f"{k}={v:.0f}" for k, v in s.items()) + f" {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect()
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
