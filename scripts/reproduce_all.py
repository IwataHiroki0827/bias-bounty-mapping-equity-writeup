"""Best Documentation の1コマンド再現: 特徴テーブルの作成から最良提出の作り直しと照合まで。

各段は出力が揃っていれば飛ばす(--fresh で全部やり直す)。新しいクローンからなら約25分(リモート集計が大半、CPU のみ)。
共有マシンでは DUCKDB_MEMORY_LIMIT=3GB・DUCKDB_THREADS=4 を推奨。
最後に、docs/probe_log.csv(LB から返った公開スコアの記録だけ)から重みを解き直し、submissions/ の提出済み CSV と照合する。

使い方: python scripts/reproduce_all.py [--fresh]
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS  # noqa: E402

P = ROOT / "data" / "processed"

# (スクリプト, その段が作る出力)。出力が全部あれば飛ばす
STEPS = [
    ("build_features.py", [P / f"features_{r}.parquet" for r in REGIONS]),
    ("discovery_sources.py", [P / "features_all.parquet"]),
    ("build_route_features.py", [P / f"routes_{r}.parquet" for r in REGIONS]),
    ("build_boundary_features.py", [P / f"boundary_{r}.parquet" for r in REGIONS]),
    ("build_tiger_proxy.py", [P / f"tiger_proxy_{r}.parquet" for r in REGIONS]),
    ("build_poi_features.py", [P / f"poi_{r}.parquet" for r in REGIONS]),
    ("fetch_ruca.py", [P / "ruca_all.parquet"]),
    ("build_road_hyp.py", [P / f"road_hyp_{r}.parquet" for r in REGIONS]),
    # lin_b2yf(最終選択の1本目)に要る分: 陸域面積(fire_partial の λ)・消防の建物・基準 v2 の予測ビン(ybin2・ybin3)
    ("fetch_strata_extra.py", [P / "strata_extra.parquet"]),
    ("build_bldg_facility.py", [P / f"bldg_facility_{r}.parquet" for r in REGIONS]),
    ("yhat_bins.py", [P / "yhat_base.parquet"]),
]


def main() -> None:
    fresh = "--fresh" in sys.argv
    t_all = time.time()
    for script, outputs in STEPS:
        if not fresh and all(o.exists() for o in outputs):
            print(f"[skip] {script}(出力あり)")
            continue
        t0 = time.time()
        print(f"[run ] {script}", flush=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], check=True)
        print(f"[done] {script} {time.time() - t0:.0f}s", flush=True)
    # 提出済みの結合を、公開スコアの記録だけから作り直して照合する
    print("[run ] reproduce_submission.py(lin_v3・lin_v5・alt_nofac・lin_v6p・lin_b2yf)", flush=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "reproduce_submission.py"), "all"], check=True)
    print(f"合計 {time.time() - t_all:.0f}s")


if __name__ == "__main__":
    main()
