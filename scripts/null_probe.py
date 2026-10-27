"""10/11 の候補プローブの null(lin_v6′ の特徴の線形射影から予測される相関)。採点される行のモーメント。
probe.py が表示する相関は全 9,794 行のモーメントなので、比較用に両方を出す。
使い方: python scripts/null_probe.py <特徴名> ...(判定は |実測(採点行) − null| > 0.015)"""
import sys
from pathlib import Path

import numpy as np

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
X = np.column_stack([c[f].to_numpy(float)[mask] for f in V6])
S = np.cov(X, rowvar=False, bias=True)
b = np.linalg.solve(S, np.array([p[f]["cov"] for f in V6]))
sd_y = np.sqrt(EY2 - EY ** 2)
for f in (sys.argv[1:] or ["rural_fire_big", "fire0_tribal", "small_core", "ratio_over", "rural_deep", "rur_x_tx"]):
    x_all = c[f].to_numpy(float)
    x = x_all[mask]
    cov_null = float(np.cov(np.column_stack([x, X]), rowvar=False, bias=True)[0, 1:] @ b)
    corr_null = cov_null / (x.std() * sd_y)
    # probe.py の表示(全行のモーメント)に合わせた null も出す: 採点外の WA の行は y の寄与 0 として扱われる
    extra = ""
    if f in p:
        extra = f"  実測(採点行) {p[f]['cov'] / (x.std() * sd_y):+.3f}"
    print(f"{f:14s} P {x.mean():.3f}(WA 込み {x_all.mean():.3f}) 非ゼロ {int((x > 0).sum())}  null 相関 {corr_null:+.3f}{extra}")
