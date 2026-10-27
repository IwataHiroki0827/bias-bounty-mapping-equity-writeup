"""プローブの推定誤差をブートストラップで実測する。

プローブは E[x]・E[x^2] を全 9,794 tract で計算しているが、採点は公開 30%(約 2,938 tract)だけ。
公開部分集合の E[x^2] と全体の値の差が、そのまま E[xy] の推定誤差になる。
ランダムな 30% を繰り返し抜き、相関・期待 RMSE の推定がどれだけぶれるかを測る。

使い方: python scripts/probe_noise.py [特徴 ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.features import candidates, load  # noqa: E402
from scripts.probe import EY, EY2, LOG  # noqa: E402


def main() -> None:
    probes = {}
    for line in LOG.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        probes[r["name"]] = r
    feats = sys.argv[1:] or list(probes)
    d = load()
    cands = candidates(d)
    rng = np.random.default_rng(0)
    n = len(d)
    k = round(n * 0.3)
    sd_y = np.sqrt(EY2 - EY ** 2)
    for f in feats:
        if f not in probes:
            continue
        x = cands[f].to_numpy(float)
        rmse = probes[f]["rmse"]
        corrs = []
        for _ in range(2000):
            idx = rng.choice(n, k, replace=False)
            m1, m2 = x[idx].mean(), (x[idx] ** 2).mean()
            exy = (EY2 + m2 - rmse ** 2) / 2
            corrs.append((exy - m1 * EY) / (np.sqrt(m2 - m1 ** 2) * sd_y))
        corrs = np.array(corrs)
        print(f"{f:14s} 点推定 {probes[f]['corr']:+.3f}  部分集合のぶれ: SD {corrs.std():.3f}  "
              f"95%区間 [{np.percentile(corrs, 2.5):+.3f}, {np.percentile(corrs, 97.5):+.3f}]")


if __name__ == "__main__":
    main()
