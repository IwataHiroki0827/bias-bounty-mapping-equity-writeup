"""Discovery 候補: 公共交通のバス停は地図に載っているか(GTFS 対 Overture infrastructure)。

車を持たない世帯の避難はバス停に依存する。交通事業者が公開する GTFS の停留所を「実在する停留所」とし、
各停留所の半径 R m 以内に Overture の bus_stop / bus_station / platform があるかを判定する。
未収載率を tract の層(SVI・部族・都市農村)で比べる。

外部データ(GTFS)は Best Bias Discovery に限り使用可(規約)。URL と取得日を data/raw/ext/gtfs/sources.json に記録する。
採点用の提出には使わない。

使い方: python scripts/discovery_transit.py
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import connect, ref, strata  # noqa: E402

EXT = ROOT / "data" / "raw" / "ext" / "gtfs"
R = 50
FEEDS = {
    # name: (region, url)  — Mobility Database feeds_v2.csv(2026-10-02 取得)の active なもの
    # 公式 URL は 403 だったので Mobility Database のミラー(latest.zip)を使う
    "valley_metro": ("maricopa-az", "https://files.mobilitydatabase.org/mdb-147/latest.zip"),
    "via_san_antonio": ("south-central-tx", "https://files.mobilitydatabase.org/tld-217/latest.zip"),
    "tulsa_transit": ("eastern-ok", "https://files.mobilitydatabase.org/tld-235/latest.zip"),
    "trax_tehama": ("northern-ca", "https://files.mobilitydatabase.org/mdb-116/latest.zip"),
    "spokane_sta": ("eastern-wa", "https://www.spokanetransit.com/gtfs"),
    "yakima_transit": ("eastern-wa", "https://yakimatransit.org/gtfs/yakima_gtfs.zip"),
    "ben_franklin": ("eastern-wa", "https://myride.bft.org/Static/google_transit.zip"),
    "pahto_yakama": ("eastern-wa", "https://data.trilliumtransit.com/gtfs/pahtopublicpassage-wa-us/pahtopublicpassage-wa-us.zip"),
    "pfp_yakima": ("eastern-wa", "https://data.trilliumtransit.com/gtfs/pfp-wa-us/pfp-wa-us.zip"),
    # 同じ州・同じ地域の比較対象(2026-10-03 追加): VIA だけが低いのか、テキサスの大手が共通して低いのか
    "houston_metro": ("south-central-tx", "https://files.mobilitydatabase.org/mdb-2060/latest.zip"),
    "dart_dallas": ("south-central-tx", "https://files.mobilitydatabase.org/mdb-152/latest.zip"),
    "capmetro_austin": ("south-central-tx", "https://files.mobilitydatabase.org/mdb-150/latest.zip"),
    "trinity_fortworth": ("south-central-tx", "https://files.mobilitydatabase.org/mdb-885/latest.zip"),
    "ccrta_corpus": ("south-central-tx", "https://files.mobilitydatabase.org/mdb-315/latest.zip"),
    # 北CA 地域(Sacramento 郡が 201 tract で最大)の事業者(2026-10-05 追加): テキサス以外の大都市でも同じかを見る
    "sacrt_sacramento": ("northern-ca", "https://files.mobilitydatabase.org/mdb-2137/latest.zip"),
    "roseville_transit": ("northern-ca", "https://files.mobilitydatabase.org/mdb-1067/latest.zip"),
    "unitrans_davis": ("northern-ca", "https://files.mobilitydatabase.org/mdb-82/latest.zip"),
    "yuba_sutter": ("northern-ca", "https://files.mobilitydatabase.org/mdb-79/latest.zip"),
    "placer_county": ("northern-ca", "https://files.mobilitydatabase.org/mdb-77/latest.zip"),
    "el_dorado": ("northern-ca", "https://files.mobilitydatabase.org/mdb-75/latest.zip"),
    "raba_redding": ("northern-ca", "https://files.mobilitydatabase.org/mdb-3031/latest.zip"),
    "bline_chico": ("northern-ca", "https://files.mobilitydatabase.org/ntd-90208/latest.zip"),
}


def fetch_stops() -> pd.DataFrame:
    EXT.mkdir(parents=True, exist_ok=True)
    src_log = EXT / "sources.json"
    log = json.loads(src_log.read_text(encoding="utf-8")) if src_log.exists() else {}
    frames = []
    for name, (region, url) in FEEDS.items():
        zpath = EXT / f"{name}.zip"
        if not zpath.exists():
            r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200 or not r.content.startswith(b"PK"):
                print(f"[NG] {name}: HTTP {r.status_code}")
                continue
            zpath.write_bytes(r.content)
            log[name] = {"url": url, "retrieved": date.today().isoformat(), "bytes": len(r.content)}
        with zipfile.ZipFile(zpath) as z:
            st = pd.read_csv(io.BytesIO(z.read("stops.txt")), dtype=str)
        lt = st.get("location_type", pd.Series("0", index=st.index)).fillna("0").replace("", "0")
        st = st[lt.isin(["0"])].copy()
        st["feed"], st["region"] = name, region
        frames.append(st[["feed", "region", "stop_id", "stop_name", "stop_lat", "stop_lon"]])
        print(f"[{name}] stops={len(st)}")
    src_log.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    df = pd.concat(frames, ignore_index=True)
    df[["stop_lat", "stop_lon"]] = df[["stop_lat", "stop_lon"]].astype(float)
    return df


def main() -> None:
    stops = fetch_stops()
    con = connect()
    con.register("stops_df", stops)
    out = []
    for region in stops["region"].unique():
        m = "ST_Transform({g}, 'EPSG:4326', 'EPSG:5070', always_xy := true)"
        con.sql(f"""CREATE OR REPLACE TEMP TABLE s AS SELECT *, {m.format(g='ST_Point(stop_lon, stop_lat)')} AS g,
                    ST_Point(stop_lon, stop_lat) AS g84 FROM stops_df WHERE region = '{region}'""")
        con.sql(f"""CREATE OR REPLACE TEMP TABLE o AS SELECT {m.format(g='ST_Centroid(geometry)')} AS g
                    FROM {ref(region, 'overture-infrastructure')}
                    WHERE class IN ('bus_stop', 'bus_station', 'platform', 'stop_position')""")
        df = con.sql(f"""
            WITH t AS (SELECT GEOID, geometry AS g FROM {strata(region, 'census-tracts')}),
                 st AS (SELECT s.*, t.GEOID FROM s LEFT JOIN t ON ST_Within(s.g84, t.g))
            SELECT st.feed, st.region, st.stop_id, st.stop_name, st.GEOID,
                   EXISTS (SELECT 1 FROM o WHERE ST_DWithin(o.g, st.g, {R})) AS mapped
            FROM st
        """).df()
        out.append(df)
    res = pd.concat(out, ignore_index=True)
    stg = pd.concat([con.sql(f"SELECT GEOID, ur_class, tribal_any, svi_overall, pop_total FROM {strata(r)}").df()
                     for r in res["region"].unique()])
    res = res.merge(stg, on="GEOID", how="left")
    res.to_parquet(ROOT / "data" / "processed" / "transit_stops.parquet", index=False)
    res["svi_q"] = pd.cut(res["svi_overall"], [-0.01, 0.25, 0.5, 0.75, 1.0], labels=["Q1低", "Q2", "Q3", "Q4高"])
    print("\n事業者別の収載率")
    print(res.groupby("feed")["mapped"].agg(["size", "mean"]).round(3).to_string())
    for by in ("ur_class", "tribal_any", "svi_q"):
        print(f"\n{by} 別(地域×層)")
        print(res.groupby(["region", by], observed=True)["mapped"].agg(["size", "mean"]).round(3).to_string())


if __name__ == "__main__":
    main()
