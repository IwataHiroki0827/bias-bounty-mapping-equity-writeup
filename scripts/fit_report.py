"""結合の候補(特徴の組)をまとめて比べる: 期待 RMSE と、基準提出との予測の相関。未プローブの特徴を含む組は飛ばす。

プローブ結果が出たら、すぐに「1本目(最良)」と「2本目(誤り方の違う版: 相関 0.98 未満)」を選ぶための表。
docs/final_selection.md の基準: 改善は期待で 0.0012 以上、2本目は相関 0.98 未満・期待の差 0.003 以内。
使い方: python scripts/fit_report.py [--base submissions/lin_v3.csv]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.features import candidates, load  # noqa: E402
from scripts.fit_linear import latest_probes  # noqa: E402
from scripts.probe import EY, EY2  # noqa: E402

REG = ["c1x_eastern-ok", "c1x_eastern-wa", "c1x_maricopa-az", "c1x_northern-ca", "c1x_south-central-tx"]
# comp_v1 と併用するときは、和が comp_v1 になるので1本(東WA = 導出値)を外す
REG4 = [r for r in REG if r != "c1x_eastern-wa"]
FIRE = ["fire_none", "fire_misfiled", "poi_short"]
SETS = {
    "lin_v3": ["comp_v1", "c1x_south-central-tx", "c1x_eastern-ok", "t_k14"] + FIRE,
    "core_k14+reg5+fire": ["comp_k14", "t_k14"] + REG + FIRE,
    "core_k14+reg5+fire+h2": ["comp_k14", "t_k14", "t_h2b05"] + REG + FIRE,
    "core_k14+reg5+fire+h2+fm": ["comp_k14", "t_k14", "t_h2b05", "t_fm_only"] + REG + FIRE,
    "all_probed_road": ["comp_k14", "t_k14", "t_h2b05", "t_fm_only", "road_undef", "t_pos"] + REG + FIRE,
    "+fire_flags": ["comp_k14", "t_k14", "t_h2b05", "t_fm_only", "road_undef", "t_pos", "fire0_rural", "fire0_prot"]
                   + REG + FIRE,
    "alt_road+region": ["comp_v1", "t_k14", "t_h2b05"] + REG4,
    "alt_road_only": ["t_k14", "t_h2b05", "t_fm_only"],
}


def main() -> None:
    base_path = Path(sys.argv[sys.argv.index("--base") + 1]) if "--base" in sys.argv else ROOT / "submissions" / "lin_v3.csv"
    base = pd.read_csv(base_path)["coverage_gap_score"].to_numpy()
    probes = latest_probes()
    c = candidates(load())
    var_y = EY2 - EY ** 2
    rows = []
    for name, feats in SETS.items():
        missing = [f for f in feats if f not in probes]
        if missing:
            rows.append({"set": name, "n": len(feats), "expected": None, "corr_base": None, "missing": ",".join(missing)})
            continue
        X = np.column_stack([c[f].to_numpy(float) for f in feats])
        S = np.cov(X, rowvar=False, bias=True)
        cv = np.array([probes[f]["cov"] for f in feats])
        b = np.linalg.solve(S, cv)
        pred = np.clip(EY - b @ X.mean(axis=0) + X @ b, 0, 1)
        rows.append({"set": name, "n": len(feats), "expected": round(float(np.sqrt(max(var_y - cv @ b, 0))), 5),
                     "corr_base": round(float(np.corrcoef(base, pred)[0, 1]), 4), "missing": ""})
    pd.set_option("display.width", 200)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
