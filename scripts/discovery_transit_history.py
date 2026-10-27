"""公共交通 Discovery の機構の確認: Overture のバス停が「一括取り込み」で入ったかを、出典と最終更新日の分布で見る。

Overture infrastructure の sources[].dataset と update_time を、停留所のある郡ごと・年ごとに数える。
一括取り込みなら、一つの郡の停留所の多くが同じ時期・同じ出典に集中するはず。
出力: data/processed/transit_history.parquet(郡×出典×年の件数)
使い方: python scripts/discovery_transit_history.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import connect, ref, strata  # noqa: E402

REGIONS = ["south-central-tx", "maricopa-az", "eastern-ok", "eastern-wa"]
CLASSES = "('bus_stop', 'bus_station', 'platform', 'stop_position')"


def main() -> None:
    con = connect()
    frames = []
    for region in REGIONS:
        df = con.sql(f"""
            WITH o AS (
                SELECT geometry AS g, class, sources[1].dataset AS dataset,
                       try_cast(sources[1].update_time AS TIMESTAMP) AS ut
                FROM {ref(region, 'overture-infrastructure')}
                WHERE class IN {CLASSES}
            ), t AS (SELECT GEOID, geometry AS g FROM {strata(region, 'census-tracts')})
            SELECT substr(t.GEOID, 1, 5) AS county, o.class, o.dataset, year(o.ut) AS yr, count(*) AS n
            FROM o JOIN t ON ST_Within(ST_Centroid(o.g), t.g)
            GROUP BY ALL
        """).df()
        df["region"] = region
        frames.append(df)
        print(region, int(df["n"].sum()), flush=True)
    import pandas as pd
    out = pd.concat(frames, ignore_index=True)
    out.to_parquet(ROOT / "data" / "processed" / "transit_history.parquet", index=False)
    focus = {"48201": "Harris/Houston", "48029": "Bexar/San Antonio", "48453": "Travis/Austin",
             "48113": "Dallas", "48355": "Nueces/Corpus Christi", "48439": "Tarrant/Fort Worth",
             "40143": "Tulsa", "04013": "Maricopa", "53063": "Spokane", "53077": "Yakima"}
    f = out[out["county"].isin(focus)].copy()
    f["county"] = f["county"].map(focus)
    print(f.groupby(["county", "dataset"])["n"].sum().unstack(fill_value=0).to_string())
    print(f.pivot_table(index="county", columns="yr", values="n", aggfunc="sum", fill_value=0).to_string())


if __name__ == "__main__":
    main()
