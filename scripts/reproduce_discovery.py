"""Best Bias Discovery(公共交通)の数字を1コマンドで再現し、writeup の値と照合する。

手順(各段は出力があれば飛ばす。--fresh で全部やり直す):
  1. GTFS 22 フィードの取得            scripts/discovery_transit.py の fetch_stops(data/raw/ext/gtfs/*.zip)
  2. ACS B08201(車の保有台数)の取得   scripts/fetch_acs_vehicles.py(data/raw/ext/acs_vehicles.parquet)
  3. 停留所と Overture の距離          scripts/discovery_transit_robust.py(リモート DuckDB、約10分)
  4. 事業者別・tract 別の集計          scripts/transit_summary.py
  5. 出典と最終更新年の集計            scripts/discovery_transit_history.py(リモート DuckDB、約5分)
  6. 図: scripts/discovery_figures.py(docs/figures/*.png)
  7. 照合: writeup の主要な数字を出力から計算し直し、期待値と比べて PASS / FAIL を出す

GTFS の latest.zip は事業者の更新で変わる。取得したファイルの SHA-256 を docs/discovery_manifest.json に記録し、
照合時に一致を確かめる(一致しなければ「データが新しい」と表示し、数字のずれはそのせいと分かるようにする)。

使い方: python scripts/reproduce_discovery.py [--fresh] [--check-only]
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402

P = ROOT / "data" / "processed"
EXT = ROOT / "data" / "raw" / "ext"
MANIFEST = ROOT / "docs" / "discovery_manifest.json"

# writeup(docs/writeup_discovery_draft.md)に載せた値。率は ±0.002、件数は完全一致で照合する
EXPECTED_RATE = {
    "tulsa_transit": (1191, 0.996), "capmetro_austin": (2336, 0.991), "ccrta_corpus": (1407, 0.925),
    "ben_franklin": (876, 0.922), "spokane_sta": (1639, 0.910), "valley_metro": (8021, 0.835),
    "trax_tehama": (107, 0.785), "dart_dallas": (6976, 0.548), "yakima_transit": (634, 0.543),
    "trinity_fortworth": (1573, 0.451), "pfp_yakima": (94, 0.245), "via_san_antonio": (6098, 0.171),
    "houston_metro": (8797, 0.148), "pahto_yakama": (33, 0.030),
    # 北CA 地域(2026-10-05 追加)
    "roseville_transit": (193, 0.990), "yuba_sutter": (289, 0.965), "sacrt_sacramento": (1748, 0.902),
    "el_dorado": (50, 0.900), "raba_redding": (309, 0.854), "unitrans_davis": (32, 0.625),
    "bline_chico": (483, 0.251), "placer_county": (151, 0.166),
}
EXPECTED_NOCAR_MAJ_UNMAPPED = {"houston_metro": 89960, "via_san_antonio": 40598, "dart_dallas": 25272,
                               "trinity_fortworth": 10218}
# 同じ tract の車なし世帯の人数(下限。4人以上世帯は4人と数える)
EXPECTED_NOCAR_PERSONS = {"houston_metro": 161300, "via_san_antonio": 69267, "dart_dallas": 44942,
                          "trinity_fortworth": 16369}
EXPECTED_R2 = {"need only": 0.043, "agency only": 0.363, "agency + need": 0.374}  # 22 事業者(10/5)
_LICENSED = ["houston_metro", "via_san_antonio", "capmetro_austin", "valley_metro", "ccrta_corpus", "sacrt_sacramento",
             "roseville_transit"]
# 利用条件が明示されたフィードだけ(10/10、docs/gtfs_licenses.md): (表示名, フィード, (停留所数, 事業者, 必要度))
EXPECTED_R2_LICENSED = [("7 本", _LICENSED, (28453, 0.440, 0.030)),
                        ("6 本・VIA 除く", [f for f in _LICENSED if f != "via_san_antonio"], (22362, 0.453, 0.018))]
EXPECTED_BURST = {"40143": (2026, 1575, 1594), "48453": (2025, 2108, 2325), "04013": (2025, 6227, 6687),
                  "48355": (2020, 1192, 1267)}
EXPECTED_MAX_YEAR = {"48201": (331, 829), "48029": (165, 788)}
# 最寄りの交通地物までの距離(探索は 1km まで。範囲外は「1km 以内に無い」= 無限大として扱う)
EXPECTED_DEST = {("houston_metro", "medical"): (7, 12), ("houston_metro", "school"): (6, 6),
                 ("via_san_antonio", "medical"): (4, 8), ("via_san_antonio", "school"): (18, 22),
                 ("capmetro_austin", "medical"): (0, 2), ("capmetro_austin", "school"): (0, 11)}
EXPECTED_TRIBAL = (0.914, 0.538)  # tribal_any の停留所の収載率(部族 / それ以外)。スコアカードの層で逆転して見える
EXPECTED_NEAREST = {"houston_metro": (386, 845), "via_san_antonio": (473, 906)}
# 本文の郡別 Overture bus_stop 件数(10/3 の集計値。class 別の history で照合する。未照合のうちは表示だけ)
EXPECTED_BUSSTOP = {"48029": 739, "48453": 2276, "48355": 1261, "48113": 3569}
# 気候リスクの高い tract(南中部TX の上位25%)にある未収載停留所: (feed, 列) → 件数
EXPECTED_HEAT = {("houston_metro", "gehe_wbgt30_days_mean"): 5729, ("houston_metro", "cvi_overall"): 4848,
                 ("via_san_antonio", "cvi_overall"): 2588}


def run(script: str) -> None:
    print(f"\n### {script}", flush=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / script)], check=True)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(fresh: bool) -> None:
    from scripts.discovery_transit import FEEDS, fetch_stops
    if fresh or any(not (EXT / "gtfs" / f"{n}.zip").exists() for n in FEEDS):
        fetch_stops()
    acs = EXT / "acs_vehicles.parquet"
    if fresh or not acs.exists() or "persons_no_vehicle_lb" not in pd.read_parquet(acs).columns:
        run("fetch_acs_vehicles.py")
    if fresh or not (P / "transit_robust.parquet").exists():
        run("discovery_transit_robust.py")
    run("transit_summary.py")
    if fresh or not (P / "transit_history.parquet").exists():
        run("discovery_transit_history.py")
    run("discovery_figures.py")
    if not MANIFEST.exists():
        MANIFEST.write_text(json.dumps({n: sha256(EXT / "gtfs" / f"{n}.zip") for n in FEEDS}, indent=1),
                            encoding="utf-8")
        print("manifest を作成:", MANIFEST)


def check() -> bool:
    from scripts.discovery_transit import FEEDS
    from scripts.discovery_transit_model import fit, load as load_model
    ok = True

    def verdict(name: str, cond: bool, detail: str) -> None:
        nonlocal ok
        ok &= cond
        print(f"[{'PASS' if cond else 'FAIL'}] {name}: {detail}")

    if MANIFEST.exists():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        changed = [n for n in FEEDS if (EXT / "gtfs" / f"{n}.zip").exists() and sha256(EXT / "gtfs" / f"{n}.zip") != man.get(n)]
        print("GTFS が記録時と異なる:", changed or "なし")
    s = pd.read_parquet(P / "transit_robust.parquet")
    s = s[s["GEOID"].notna()]
    s["m"] = np.fmin(s["d_infra"], s["d_places"]) <= 100
    g = s.groupby("feed")["m"].agg(["size", "mean"])
    for feed, (n, rate) in EXPECTED_RATE.items():
        got_n, got_r = int(g.loc[feed, "size"]), float(g.loc[feed, "mean"])
        verdict(f"収載率 {feed}", got_n == n and abs(got_r - rate) <= 0.002, f"{got_n} 停留所 {got_r:.3f}(期待 {n} / {rate})")
    # 提言の表: 収載率 60% 未満の事業者の未収載停留所の合計
    low = g[g["mean"] < 0.6].index
    got_missing = int((~s.loc[s["feed"].isin(low), "m"]).sum())
    verdict("60% 未満の事業者の未収載停留所の合計", got_missing == 17445, f"{got_missing:,}(期待 17,445)")
    # 施設名を持つ停留所の未収載 / 件数(scripts/transit_destinations.py と同じ正規表現)
    from scripts.transit_destinations import PATTERNS
    for (feed, kind), (miss, n) in EXPECTED_DEST.items():
        g = s[(s["feed"] == feed) & s["stop_name"].fillna("").str.contains(PATTERNS[kind], case=False, regex=True)]
        got = (int((~g["m"]).sum()), len(g))
        verdict(f"施設名の停留所 {feed} {kind}", got == (miss, n), f"未収載 {got[0]}/{got[1]}(期待 {miss}/{n})")
    tb = s["tribal_any"].astype(str).str.lower().eq("true")
    got = (round(float(s.loc[tb, "m"].mean()), 3), round(float(s.loc[~tb, "m"].mean()), 3))
    verdict("部族 tract / それ以外の収載率", got == EXPECTED_TRIBAL, f"{got}(期待 {EXPECTED_TRIBAL})")
    dist = np.fmin(s["d_infra"], s["d_places"]).fillna(np.inf)
    for feed, (med, far) in EXPECTED_NEAREST.items():
        d = dist[s["feed"] == feed]
        got_med, got_far = int(round(float(d.median()))), int(np.isinf(d).sum())
        verdict(f"最寄り距離 {feed}", (got_med, got_far) == (med, far), f"中央値 {got_med}m・1km 以内に無し {got_far}(期待 {med}m・{far})")
    t = pd.read_parquet(P / "transit_tracts.parquet")
    for feed, hh in EXPECTED_NOCAR_MAJ_UNMAPPED.items():
        got = int(t[(t["feed"] == feed) & (t["mapped"] < 0.5)]["hh_no_vehicle"].sum())
        verdict(f"過半未収載 tract の車なし世帯 {feed}", got == hh, f"{got:,}(期待 {hh:,})")
    for feed, n in EXPECTED_NOCAR_PERSONS.items():
        got = int(t[(t["feed"] == feed) & (t["mapped"] < 0.5)]["persons_no_vehicle_lb"].sum())
        verdict(f"過半未収載 tract の車なし世帯の人数 {feed}", got == n, f"{got:,}(期待 {n:,})")
    d = load_model()
    y = d["mapped"].to_numpy()
    ll0 = float(np.sum(y * np.log(y.mean()) + (1 - y) * np.log(1 - y.mean())))
    need = d[["noveh_share", "svi_overall", "rural", "tribal"]]
    agency = pd.get_dummies(d["feed"], drop_first=True, dtype=float)
    for name, X in (("need only", need), ("agency only", agency), ("agency + need", pd.concat([agency, need], axis=1))):
        r2 = 1 - fit(X, y)[0] / ll0
        verdict(f"擬似R² {name}", abs(r2 - EXPECTED_R2[name]) <= 0.002, f"{r2:.3f}(期待 {EXPECTED_R2[name]})")
    # 利用条件が明示されたフィードだけでの擬似R²(docs/gtfs_licenses.md)
    for label, feeds, (n_exp, ag_exp, need_exp) in EXPECTED_R2_LICENSED:
        dd = d[d["feed"].isin(feeds)]
        yy = dd["mapped"].to_numpy()
        l0 = float(np.sum(yy * np.log(yy.mean()) + (1 - yy) * np.log(1 - yy.mean())))
        ag = 1 - fit(pd.get_dummies(dd["feed"], drop_first=True, dtype=float), yy)[0] / l0
        nd = 1 - fit(dd[["noveh_share", "svi_overall", "rural", "tribal"]], yy)[0] / l0
        ok_ = len(dd) == n_exp and abs(ag - ag_exp) <= 0.002 and abs(nd - need_exp) <= 0.002
        verdict(f"擬似R²(条件明示の {label})", ok_, f"{len(dd):,} 停留所 事業者 {ag:.3f} 必要度 {nd:.3f}(期待 {n_exp:,} / {ag_exp} / {need_exp})")
    h = pd.read_parquet(P / "transit_history.parquet")
    by = h.groupby(["county", "yr"])["n"].sum()
    for county, (yr, n, total) in EXPECTED_BURST.items():
        got_n, got_t = int(by.get((county, yr), 0)), int(by.loc[county].sum())
        verdict(f"一括更新の年 {county}", (got_n, got_t) == (n, total), f"{yr}年 {got_n}/{got_t}(期待 {n}/{total})")
    for county, (mx, total) in EXPECTED_MAX_YEAR.items():
        got_mx, got_t = int(by.loc[county].max()), int(by.loc[county].sum())
        verdict(f"集中年なし {county}", (got_mx, got_t) == (mx, total), f"最多の年 {got_mx}/{got_t}(期待 {mx}/{total})")
    # 本文の郡別 bus_stop 件数(Overpass の OSM 実数と並べる値)。class 列のある集計でだけ照合する
    if "class" in h.columns:
        bs = h[h["class"] == "bus_stop"].groupby("county")["n"].sum()
        for county, n in EXPECTED_BUSSTOP.items():
            got = int(bs.get(county, 0))
            verdict(f"bus_stop 件数 {county}", got == n, f"{got:,}(期待 {n:,})")
    import io
    import requests
    from scripts.transit_heat import COLS, URL
    st = pd.read_csv(io.StringIO(requests.get(URL, headers={"User-Agent": "curl/8"}, timeout=120).text),
                     dtype={"GEOID": str}, usecols=COLS)
    un = s[~s["m"]].merge(st, on="GEOID", how="left")
    for (feed, col), n in EXPECTED_HEAT.items():
        got = int(((un["feed"] == feed) & (un[col] >= st[col].quantile(0.75))).sum())
        verdict(f"気候リスク上位25% の未収載 {feed} {col}", got == n, f"{got:,}(期待 {n:,})")
    return ok


def main() -> None:
    if "--check-only" not in sys.argv:
        build("--fresh" in sys.argv)
    print("\n### 照合")
    ok = check()
    print("\n結果:", "すべて一致" if ok else "不一致あり(GTFS が更新されていればそのため)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
