"""事業所半分(Overture places / CBP 事業所)の推定用に、Overture places の供給元(sources[].dataset)を tract ごとに数える。

仮説 P4(10/14): 米国の places は Meta・BrightQuery・Microsoft・Foursquare 等の合成。供給元ごとの件数の構成が
tract で違えば、CBP の事業所に対する欠け方も違う。1件に複数の供給元が付くことがあるので、
供給元ごとの「その供給元を含む件数」と、供給元が1つだけの件数を数える。

出力: data/processed/place_sources_<region>.parquet(地域ごとに上書き。溜まらない)
使い方: python scripts/build_place_sources.py [region ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref, strata  # noqa: E402

OUT = ROOT / "data" / "processed"


def build(con, region: str) -> None:
    t0 = time.time()
    df = con.sql(f"""
        WITH p AS (
            SELECT geometry AS g, list_transform(sources, s -> s.dataset) AS ds
            FROM {ref(region, 'overture-pois')}
        ), t AS (SELECT GEOID, geometry AS g FROM {strata(region, 'census-tracts')}),
        j AS (SELECT t.GEOID, p.ds FROM p JOIN t ON ST_Within(p.g, t.g)),
        u AS (SELECT GEOID, d AS dataset, len(list_distinct(ds)) AS nsrc FROM j, unnest(list_distinct(ds)) AS x(d))
        SELECT GEOID, dataset, count(*) AS n, count(*) FILTER (WHERE nsrc = 1) AS n_only
        FROM u GROUP BY 1, 2
    """).df()
    wide = df.pivot_table(index="GEOID", columns="dataset", values=["n", "n_only"], fill_value=0)
    wide.columns = [f"ps_{a}_{b}".replace(" ", "_") for a, b in wide.columns]
    wide = wide.reset_index()
    wide.to_parquet(OUT / f"place_sources_{region}.parquet", index=False)
    tot = df.groupby("dataset")["n"].sum().sort_values(ascending=False)
    print(f"[{region}] tracts={len(wide)} {time.time() - t0:.0f}s  " + ", ".join(f"{k}={v}" for k, v in tot.items()), flush=True)


def main() -> None:
    con = connect(threads=4)
    con.sql("SET memory_limit = '2GB'")
    for region in sys.argv[1:] or REGIONS:
        build(con, region)


if __name__ == "__main__":
    main()
