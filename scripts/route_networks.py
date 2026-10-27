"""Overture 道路の routes[].network の種類と延長を、道路クラス別・地域別に数える(道路推定の取りこぼし調査)。

番号つき路線の近似(I / US / 州道)に入れていない network(郡道 US:TX:CR など)が、幹線クラスにどれだけあるかを見る。
出力: data/processed/route_networks.parquet(地域 × network の種類 × クラスの延長 km)
使い方: python scripts/route_networks.py [region ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS, connect, ref  # noqa: E402
from scripts.build_tiger_proxy import m  # noqa: E402


def main() -> None:
    con = connect(threads=2)
    con.sql("SET memory_limit='1500MB'")  # 受付への申告値
    frames = []
    for region in sys.argv[1:] or REGIONS:
        df = con.sql(f"""
            WITH r AS (
                SELECT class, ST_Length({m('geometry')}) / 1000 AS km,
                       list_distinct(list_transform(coalesce(routes, []),
                           x -> regexp_replace(coalesce(x.network, '(none)'), ':[^:]*$', ':*'))) AS nets
                FROM {ref(region, 'overture-roads')}
                WHERE class IN ('motorway', 'trunk', 'primary', 'secondary', 'tertiary')
            )
            SELECT class, coalesce(net, '(no route)') AS network_family, sum(km) AS km, count(*) AS segments
            FROM (SELECT class, km, unnest(CASE WHEN len(nets) = 0 THEN [NULL] ELSE nets END) AS net FROM r)
            GROUP BY ALL
        """).df()
        df["region"] = region
        frames.append(df)
        print(f"[{region}] {df['km'].sum():.0f} km", flush=True)
    out = pd.concat(frames, ignore_index=True)
    out.to_parquet(ROOT / "data" / "processed" / "route_networks.parquet", index=False)
    top = out.groupby(["region", "network_family"])["km"].sum().reset_index()
    for region, g in top.groupby("region"):
        print(f"\n== {region}")
        print(g.sort_values("km", ascending=False).head(12).round(0).to_string(index=False))


if __name__ == "__main__":
    main()
