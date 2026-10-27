"""F2・F4(10/18 Fable): 消防署の座標ずれ(境界の外側の署)と categories.alternate の消防・学校を tract ごとに数える。

機構(F2): 参照(撤去済み)の消防署の座標は住所ジオコードで、Overture places は建物位置。署が tract 境界の近くにあると、
参照では tract A、Overture では隣の tract B に落ちうる。A は「参照に署あり・地図に無し」で消防の gap が 1 になる。
機構(F4): 採点は categories.primary だけで施設種別を判定する。alternate に fire_department / school を持つ places は
採点では数えられないが、実在の施設の目印になる。
消防の点 = places の fire_department、名前が消防署の places、建物の class=fire_station または名前が消防署(F1 と同じ規則)。
出力: data/processed/facnear_<region>.parquet(地域ごとに上書き)
使い方: python scripts/build_facility_near.py [region ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.build_poi_features import FIRE_NAME, FIRE_NOT, SCHOOL_CATS  # noqa: E402
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref, strata  # noqa: E402

OUT = ROOT / "data" / "processed"


def m(g: str) -> str:
    return f"ST_Transform({g}, 'EPSG:4326', 'EPSG:5070', always_xy := true)"


def build(con, region: str) -> None:
    t0 = time.time()
    sc = ", ".join(f"'{c}'" for c in SCHOOL_CATS)
    fire_nm = f"(regexp_matches(nm, '{FIRE_NAME}') AND NOT regexp_matches(nm, '{FIRE_NOT}'))"
    df = con.sql(f"""
        WITH p AS (
            SELECT geometry AS g, categories.primary AS cat, coalesce(categories.alternate, []) AS alt,
                   lower(coalesce(names.primary, '')) AS nm
            FROM {ref(region, 'overture-pois')}
        ), pf AS (
            SELECT {m('g')} AS g FROM p WHERE cat = 'fire_department' OR {fire_nm}
        ), bf AS (
            SELECT {m('ST_PointOnSurface(geometry)')} AS g FROM (
                SELECT geometry, class AS cl, lower(coalesce(names.primary, '')) AS nm
                FROM {ref(region, 'overture-buildings')}
                WHERE class = 'fire_station' OR names.primary IS NOT NULL
            ) WHERE cl = 'fire_station' OR {fire_nm}
        ), fp AS (SELECT g FROM pf UNION ALL SELECT g FROM bf),
        t AS (SELECT GEOID, {m('geometry')} AS g FROM {strata(region, 'census-tracts')}),
        nb AS (
            SELECT t.GEOID,
                   count(*) FILTER (WHERE ST_DWithin(fp.g, t.g, 150)) AS nb_fire150_n,
                   count(*) FILTER (WHERE ST_DWithin(fp.g, t.g, 50)) AS nb_fire50_n
            FROM t JOIN fp ON ST_DWithin(fp.g, t.g, 150) AND NOT ST_Within(fp.g, t.g)
            GROUP BY 1
        ), ed AS (
            SELECT t.GEOID, count(*) AS edge_fire50_n
            FROM t JOIN fp ON ST_Within(fp.g, t.g) AND ST_DWithin(fp.g, ST_Boundary(t.g), 50)
            GROUP BY 1
        ), al AS (
            SELECT t.GEOID,
                   count(*) FILTER (WHERE cat IS DISTINCT FROM 'fire_department' AND list_contains(alt, 'fire_department')) AS alt_fire_n,
                   count(*) FILTER (WHERE cat NOT IN ({sc}) AND list_has_any(alt, [{sc}])) AS alt_school_n
            FROM t JOIN (SELECT {m('g')} AS g, cat, alt FROM p
                         WHERE list_contains(alt, 'fire_department') OR list_has_any(alt, [{sc}])) q
              ON ST_Within(q.g, t.g)
            GROUP BY 1
        )
        SELECT t.GEOID,
               coalesce(nb.nb_fire150_n, 0) AS nb_fire150_n, coalesce(nb.nb_fire50_n, 0) AS nb_fire50_n,
               coalesce(ed.edge_fire50_n, 0) AS edge_fire50_n,
               coalesce(al.alt_fire_n, 0) AS alt_fire_n, coalesce(al.alt_school_n, 0) AS alt_school_n
        FROM t LEFT JOIN nb USING (GEOID) LEFT JOIN ed USING (GEOID) LEFT JOIN al USING (GEOID)
    """).df()
    df.to_parquet(OUT / f"facnear_{region}.parquet", index=False)
    s = (df.drop(columns="GEOID") > 0).sum()
    print(f"[{region}] tracts={len(df)} " + " ".join(f"{k}>0:{v}" for k, v in s.items()) + f" {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    con = connect(threads=4)
    con.sql("SET memory_limit = '2GB'")
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
