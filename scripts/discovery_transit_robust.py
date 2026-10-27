"""公共交通 Discovery の頑健性確認。

discovery_transit.py が取得した GTFS 停留所(data/raw/ext/gtfs/*.zip)について、
  1. 最寄りの Overture infrastructure(bus_stop 等)までの距離 → 半径 25/50/100/200 m での収載率
  2. Overture places のうち交通系カテゴリ・名前(bus, transit, station 等)までの距離 → places 側の収載
  3. 各フィードの性格: 予約制・区間乗降(GTFS の booking_rules / pickup_type / location_groups の有無)
を出す。結果は data/processed/transit_robust.parquet。

使い方: python scripts/discovery_transit_robust.py
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import connect, ref, strata  # noqa: E402
from scripts.discovery_transit import EXT, FEEDS  # noqa: E402

RADII = (25, 50, 100, 200)
M = "ST_Transform({g}, 'EPSG:4326', 'EPSG:5070', always_xy := true)"


def feed_profile(name: str) -> dict:
    with zipfile.ZipFile(EXT / f"{name}.zip") as z:
        names = set(z.namelist())
        prof = {"feed": name, "files": len(names),
                "booking_rules": "booking_rules.txt" in names,
                "location_groups": "location_groups.txt" in names or "locations.geojson" in names}
        if "stop_times.txt" in names:
            stt = pd.read_csv(io.BytesIO(z.read("stop_times.txt")), dtype=str, usecols=lambda c: c in
                              ("stop_id", "pickup_type", "drop_off_type", "continuous_pickup"))
            pt = stt.get("pickup_type", pd.Series(dtype=str)).fillna("0")
            prof["stop_times"] = len(stt)
            prof["pickup_phone_share"] = round(float((pt == "2").mean()), 3) if len(stt) else None
            prof["pickup_none_share"] = round(float((pt == "1").mean()), 3) if len(stt) else None
        # 運行期間(古いフィードは注記する)
        if "calendar.txt" in names:
            cal = pd.read_csv(io.BytesIO(z.read("calendar.txt")), dtype=str)
            prof["service"] = f"{cal['start_date'].min()}-{cal['end_date'].max()}"
        elif "calendar_dates.txt" in names:
            cd = pd.read_csv(io.BytesIO(z.read("calendar_dates.txt")), dtype=str)
            prof["service"] = f"{cd['date'].min()}-{cd['date'].max()}"
        if "routes.txt" in names:
            rt = pd.read_csv(io.BytesIO(z.read("routes.txt")), dtype=str)
            prof["routes"] = len(rt)
            prof["route_names"] = "; ".join((rt.get("route_long_name", rt.get("route_short_name"))).fillna("").astype(str).head(6))
    return prof


def main() -> None:
    frames = []
    for name, (region, _) in FEEDS.items():
        if not (EXT / f"{name}.zip").exists():
            continue
        with zipfile.ZipFile(EXT / f"{name}.zip") as z:
            st = pd.read_csv(io.BytesIO(z.read("stops.txt")), dtype=str)
        lt = st.get("location_type", pd.Series("0", index=st.index)).fillna("0").replace("", "0")
        st = st[lt == "0"].copy()
        st["feed"], st["region"] = name, region
        frames.append(st[["feed", "region", "stop_id", "stop_name", "stop_lat", "stop_lon"]])
    stops = pd.concat(frames, ignore_index=True)
    stops[["stop_lat", "stop_lon"]] = stops[["stop_lat", "stop_lon"]].astype(float)

    con = connect()
    con.register("stops_df", stops)
    out = []
    for region in stops["region"].unique():
        con.sql(f"""CREATE OR REPLACE TEMP TABLE s AS SELECT *, {M.format(g='ST_Point(stop_lon, stop_lat)')} AS g
                    FROM stops_df WHERE region = '{region}'""")
        con.sql(f"""CREATE OR REPLACE TEMP TABLE oi AS SELECT {M.format(g='ST_Centroid(geometry)')} AS g
                    FROM {ref(region, 'overture-infrastructure')}
                    WHERE class IN ('bus_stop', 'bus_station', 'platform', 'stop_position')""")
        con.sql(f"""CREATE OR REPLACE TEMP TABLE op AS SELECT {M.format(g='geometry')} AS g
                    FROM {ref(region, 'overture-pois')}
                    WHERE regexp_matches(coalesce(categories.primary, ''), 'bus|transit|transportation|train_station')
                       OR regexp_matches(lower(coalesce(names.primary, '')), '\\b(bus stop|bus station|transit center|transit centre|park and ride|park & ride)\\b')""")
        df = con.sql(f"""
            SELECT s.feed, s.region, s.stop_id, s.stop_name, s.stop_lat, s.stop_lon,
                   (SELECT min(ST_Distance(oi.g, s.g)) FROM oi WHERE ST_DWithin(oi.g, s.g, 1000)) AS d_infra,
                   (SELECT min(ST_Distance(op.g, s.g)) FROM op WHERE ST_DWithin(op.g, s.g, 1000)) AS d_places
            FROM s
        """).df()
        t = con.sql(f"SELECT GEOID, geometry AS g FROM {strata(region, 'census-tracts')}")
        con.register("res_df", df)
        geo = con.sql("""SELECT r.stop_id, r.feed, t.GEOID FROM res_df r
                         JOIN (SELECT * FROM t) t ON ST_Within(ST_Point(r.stop_lon, r.stop_lat), t.g)""").df()
        df = df.merge(geo, on=["stop_id", "feed"], how="left")
        stg = con.sql(f"SELECT GEOID, ur_class, tribal_any, aiannh_name, svi_overall FROM {strata(region)}").df()
        out.append(df.merge(stg, on="GEOID", how="left"))
    res = pd.concat(out, ignore_index=True)
    res.to_parquet(ROOT / "data" / "processed" / "transit_robust.parquet", index=False)

    pd.set_option("display.width", 220)
    print("=== 事業者別: 半径ごとの infrastructure 収載率 / places を含めた収載率(100m)")
    rows = []
    for feed, g in res.groupby("feed"):
        r = {"feed": feed, "stops": len(g)}
        for rad in RADII:
            r[f"infra≤{rad}"] = round(float((g["d_infra"] <= rad).mean()), 3)
        r["infra|places≤100"] = round(float(((g["d_infra"] <= 100) | (g["d_places"] <= 100)).mean()), 3)
        rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n=== 部族 tract 別(半径ごと)")
    for rad in RADII:
        print(rad, res.groupby("tribal_any")["d_infra"].apply(lambda s: round(float((s <= rad).mean()), 3)).to_dict())
    print("\n=== フィードの性格")
    print(pd.DataFrame([feed_profile(n) for n in res["feed"].unique()]).to_string(index=False))
    print("\n=== Pahto の停留所(最寄り距離つき)")
    print(res[res.feed == "pahto_yakama"][["stop_name", "d_infra", "d_places", "aiannh_name", "ur_class"]]
          .round(0).to_string(index=False))


if __name__ == "__main__":
    main()
