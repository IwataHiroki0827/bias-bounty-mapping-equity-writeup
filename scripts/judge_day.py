"""その日のプローブを事前登録の規則で判定する(10/17〜19 用)。

null は null_probe_v2 と同じ計算(基準の特徴で説明できる相関)。採否は |実測 − null| > 0.015(採点行のモーメント)。
--extra で基準に当たりを足す(例: --extra fire_partial,t_kcty。10/18 以降は 10/16〜17 の当たりを含める)。
実測は docs/probe_log の最新(probe.py が採点後に追記する)。未採点の特徴は「未採点」と出す。
使い方: python scripts/judge_day.py ybin4 ybin3 ybin1 ybin2 t_kreg
        python scripts/judge_day.py --extra fire_partial,t_kcty t_sp45 t_tigerpar15 t_k14nn t_named t_named_fm
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fit_linear import latest_probes, scored_mask  # noqa: E402
from scripts.probe import EY, EY2  # noqa: E402
from src.features import candidates, load  # noqa: E402

THRESH = 0.015
RMSE_NOW = 0.0634  # 公開の実測(残差の SD の近似)
N_PUB = 2814       # 採点行 9,379 の 30%
# null_probe_v2 の BASE(10/14 の基準)
R4 = ["c1x_eastern-ok", "c1x_maricopa-az", "c1x_northern-ca", "c1x_south-central-tx"]
V6 = (["comp_k14", "t_k14"] + R4 + ["fire_none", "fire_misfiled", "poi_short", "road_undef", "rural_ur"]
      + ["fire0_rural", "fire0_prot", "t_pos", "school_short", "tk14_rural", "t_ter05", "unnum_share"])
BASE = V6 + ["small_core", "fire0_tribal", "ratio_over", "tk14x_south-central-tx", "tk14x_eastern-ok",
             "tk14_x_tershare", "ruca_core"]

# 事前登録の後続(docs/probe_plan.md)。当たり(偏差 > +0.015)のときに出す次の一手
FOLLOW = {
    "t_sp45": lambda dev: ("comp_sp45@0.25 を先に(生の仮説寄り)" if dev >= 0.08
                           else "t_sp45_imp@0.25 を先に(補完の仮説寄り)"),
    "t_named_fm": lambda dev: "comp_named_fm@0.25",
    "t_named": lambda dev: "comp_named@0.25(t_named_fm が外れのときだけ)",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+")
    ap.add_argument("--extra", default="", help="基準に足す当たりの特徴(カンマ区切り)")
    a = ap.parse_args()
    base = BASE + [f for f in a.extra.split(",") if f]
    d = load()
    c = candidates(d)
    mask = scored_mask(d)
    p = latest_probes(c, mask)
    X = np.column_stack([c[f].to_numpy(float)[mask] for f in base])
    b = np.linalg.solve(np.cov(X, rowvar=False, bias=True), np.array([p[f]["cov"] for f in base]))
    sd_y = np.sqrt(EY2 - EY ** 2)
    print(f"基準 {len(base)} 本(extra: {a.extra or 'なし'})/ 閾値 |偏差| > {THRESH}")
    hits = []
    for f in a.names:
        x = c[f].to_numpy(float)[mask]
        null = float(np.cov(np.column_stack([x, X]), rowvar=False, bias=True)[0, 1:] @ b) / (x.std() * sd_y)
        if f not in p:
            print(f"{f:24s} null {null:+.3f}  未採点")
            continue
        meas = p[f]["cov"] / (x.std() * sd_y)
        # 公開 30%(約 2,800 行)の抜き方による偏差の標準誤差。残差の分散割合が大きい特徴ほどぶれる
        xc = x - x.mean()
        share = float(np.var(xc - (X - X.mean(0)) @ np.linalg.lstsq(X - X.mean(0), xc, rcond=None)[0]) / x.var())
        se = np.sqrt(share) * (RMSE_NOW / sd_y) / np.sqrt(N_PUB)
        dev = meas - null
        verdict = "当たり" if dev > THRESH else ("下に外れ" if dev < -THRESH else "null")
        print(f"{f:24s} null {null:+.3f}  実測 {meas:+.3f}  偏差 {dev:+.3f}(SE {se:.3f}、{abs(dev) / se:.1f}σ)  {verdict}")
        if abs(dev) > THRESH:
            hits.append(f)
        if f in FOLLOW and dev > THRESH:
            print(f"    → 後続(事前登録): {FOLLOW[f](dev)}")
    print("当たり:", ", ".join(hits) or "なし")


if __name__ == "__main__":
    main()
