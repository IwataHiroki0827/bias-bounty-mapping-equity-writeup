"""lin_v6′ に情報のあった特徴を足した結合を、採点される行の 90% 点で比べる(10/11 版を 10/14 に更新)。
結合を出す条件: 90% 点が lin_v6′ より 0.0012 以上良い。SETS を更新して使う。"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fit_linear import latest_probes, scored_mask  # noqa: E402
from scripts.probe import EY  # noqa: E402
from scripts.robust_expected import robust  # noqa: E402
from src.features import candidates, load  # noqa: E402

ROOT = str(Path(__file__).resolve().parent.parent)
d = load()
c_all = candidates(d)
mask = scored_mask(d)
p = latest_probes(c_all, mask)
c = {k: v[mask].reset_index(drop=True) for k, v in c_all.items()}
R4 = ["c1x_eastern-ok", "c1x_maricopa-az", "c1x_northern-ca", "c1x_south-central-tx"]
V6 = (["comp_k14", "t_k14"] + R4 + ["fire_none", "fire_misfiled", "poi_short", "road_undef", "rural_ur"]
      + ["fire0_rural", "fire0_prot", "t_pos", "school_short", "tk14_rural", "t_ter05", "unnum_share"])
A = ["comp_k14", "t_k14", "road_undef"] + R4
H5 = ["small_core", "fire0_tribal", "ratio_over", "tk14x_south-central-tx", "tk14x_eastern-ok"]
SETS = {
    "lin_v6'": V6,
    "v6' + H5": V6 + H5,
    "v6' + H5 + ca + ter10": V6 + H5 + ["tk14x_northern-ca", "t_ter10_k14"],
    "v6' + H5 + tershare + ruca_core": V6 + H5 + ["tk14_x_tershare", "ruca_core"],
    "v6' + H5 + ca + ter10 + tershare + ruca_core": V6 + H5 + ["tk14x_northern-ca", "t_ter10_k14", "tk14_x_tershare", "ruca_core"],
    "... + log_aland": V6 + H5 + ["tk14x_northern-ca", "t_ter10_k14", "tk14_x_tershare", "ruca_core", "log_aland"],
    "... + log_aland + t_loc + aland": V6 + H5 + ["tk14x_northern-ca", "t_ter10_k14", "tk14_x_tershare", "ruca_core", "log_aland", "t_loc_k10", "tk14_x_aland"],
}


def pred(feats):
    X = np.column_stack([c_all[f].to_numpy(float) for f in feats])
    Xs = X[mask]
    S = np.cov(Xs, rowvar=False, bias=True)
    b = np.linalg.solve(S, np.array([p[f]["cov"] for f in feats]))
    return np.clip(EY - b @ Xs.mean(0) + X @ b, 0, 1)


alt = pd.read_csv(ROOT + r"\submissions\alt_nofac.csv")["coverage_gap_score"].to_numpy()
v6 = pd.read_csv(ROOT + r"\submissions\lin_v6p.csv")["coverage_gap_score"].to_numpy()
base = robust(V6, c, p, n_sim=300)
print(f"基準 lin_v6′ 90% 点 {base['p90']:.5f}(公開 0.063415)。採用には {base['p90'] - 0.0012:.5f} 以下")
rows = []
for name, feats in SETS.items():
    r = robust(feats, c, p, n_sim=300)
    pr = pred(feats)
    rows.append((r["p90"], name, r, np.corrcoef(pr[mask], alt[mask])[0, 1], np.corrcoef(pr[mask], v6[mask])[0, 1]))
for p90, name, r, ca, c6 in sorted(rows):
    print(f"{name:44s} 点 {r['point']:.5f} 90%点 {p90:.5f} SD {r['sd']:.5f} 最大重み {r['max_abs_w']:.3f}  相関 alt {ca:.3f} / v6′ {c6:.3f}")
