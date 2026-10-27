"""10/14: 基準を lin_v6' + 当たり7本(H5 + tershare + ruca_core)に更新した null と、
利得 2e-4(MSE)に要る相関の偏差 = sqrt(2e-4 * var(x の残差)) / (sd_x * sd_y)。採点行のモーメント。"""
import sys

import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fit_linear import latest_probes, scored_mask  # noqa: E402
from scripts.probe import EY, EY2  # noqa: E402
from src.features import candidates, load  # noqa: E402

d = load()
c = candidates(d)
mask = scored_mask(d)
p = latest_probes(c, mask)
R4 = ["c1x_eastern-ok", "c1x_maricopa-az", "c1x_northern-ca", "c1x_south-central-tx"]
V6 = (["comp_k14", "t_k14"] + R4 + ["fire_none", "fire_misfiled", "poi_short", "road_undef", "rural_ur"]
      + ["fire0_rural", "fire0_prot", "t_pos", "school_short", "tk14_rural", "t_ter05", "unnum_share"])
BASE = V6 + ["small_core", "fire0_tribal", "ratio_over", "tk14x_south-central-tx", "tk14x_eastern-ok",
             "tk14_x_tershare", "ruca_core"]
X = np.column_stack([c[f].to_numpy(float)[mask] for f in BASE])
S = np.cov(X, rowvar=False, bias=True)
b = np.linalg.solve(S, np.array([p[f]["cov"] for f in BASE]))
sd_y = np.sqrt(EY2 - EY ** 2)
Xc = X - X.mean(0)
rows = []
for f in sys.argv[1:]:
    x = c[f].to_numpy(float)[mask]
    cov_null = float(np.cov(np.column_stack([x, X]), rowvar=False, bias=True)[0, 1:] @ b)
    corr_null = cov_null / (x.std() * sd_y)
    coef, *_ = np.linalg.lstsq(Xc, x - x.mean(), rcond=None)
    var_res = float(np.var(x - x.mean() - Xc @ coef))
    need = np.sqrt(2e-4 * var_res) / (x.std() * sd_y)
    done = f" 実測 {p[f]['cov'] / (x.std() * sd_y):+.3f}" if f in p else ""
    rows.append((need, f, corr_null, var_res / x.var(), done))
for need, f, cn, share, done in sorted(rows):
    print(f"{f:24s} null {cn:+.3f}  残差割合 {share:.3f}  要る偏差 {need:.3f}{done}")
