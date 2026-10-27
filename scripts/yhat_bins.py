"""10/15 Fable の案③: 予測の分位ビンでの較正プローブ用に、基準 v2(lin_v6′ + 当たり7本、25 特徴)の予測 ŷ を書く。

線形最小二乗は全体の較正しか保証しない。ŷ のビンの 0/1 フラグを @0.12 で出すと E[y | ビン] が解け、
尾(ŷ が大きい tract)で予測が過大・過小かが分かる。フラグの定義は src/features.py の ybin1〜ybin4。
ŷ は全行で出すが、重みは採点行のモーメントで解く(null_probe_v2.py と同じ)。
使い方: python scripts/yhat_bins.py   → data/processed/yhat_base.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fit_linear import latest_probes, scored_mask  # noqa: E402
from scripts.probe import EY  # noqa: E402
from src.features import BIN_EDGES, candidates, load  # noqa: E402

R4 = ["c1x_eastern-ok", "c1x_maricopa-az", "c1x_northern-ca", "c1x_south-central-tx"]
V6 = (["comp_k14", "t_k14"] + R4 + ["fire_none", "fire_misfiled", "poi_short", "road_undef", "rural_ur"]
      + ["fire0_rural", "fire0_prot", "t_pos", "school_short", "tk14_rural", "t_ter05", "unnum_share"])
BASE = V6 + ["small_core", "fire0_tribal", "ratio_over", "tk14x_south-central-tx", "tk14x_eastern-ok",
             "tk14_x_tershare", "ruca_core"]


def main() -> None:
    d = load()
    c = candidates(d)
    mask = scored_mask(d)
    p = latest_probes(c, mask)
    X = np.column_stack([c[f].to_numpy(float) for f in BASE])
    Xs = X[mask]
    b = np.linalg.solve(np.cov(Xs, rowvar=False, bias=True), np.array([p[f]["cov"] for f in BASE]))
    yhat = EY + (X - Xs.mean(0)) @ b
    out = Path(__file__).resolve().parent.parent / "data" / "processed" / "yhat_base.parquet"
    pd.DataFrame({"GEOID": d["GEOID"], "yhat_base": yhat}).to_parquet(out, index=False)
    ys = yhat[mask]
    edges = [-np.inf, *BIN_EDGES, np.inf]
    for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        m = (ys > lo) & (ys <= hi)
        print(f"bin{i} ({lo:.2f},{hi:.2f}]  割合 {m.mean():.3f}  ŷ平均 {ys[m].mean():.4f}")
    print("書いた:", out)


if __name__ == "__main__":
    main()
