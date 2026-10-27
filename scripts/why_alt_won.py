"""なぜ施設成分なしの版(alt_nofac)が lin_v5 より良かったか(10/9)。正解は使わず、プローブの集計値だけで分解する。

(1) MSE の差の分解: 2本とも特徴の線形結合なので、Δ = MSE(v5) − MSE(alt) = E[p5² − pa²] − 2 E[(p5 − pa) y]。
    p5 − pa = Δa0 + Σ Δb_i x_i なので E[(p5 − pa) y] = Δa0·E[y] + Σ Δb_i E[x_i y]。E[x_i y] はプローブから分かる。
    特徴ごとの寄与 −2 Δb_i E[x_i y] と、予測側の E[p²] の差を並べ、実測の差(0.06641² − 0.065236²)と照合する。
(2) 集団ごとの偏り: 0/1 のプローブ済みフラグ g について、正解の集団平均 E[y|g] = E[y] + cov/P と、2本の予測の集団平均を比べる。
モーメントは採点される 9,379 tract だけで取る(eastern-wa は採点されない。10/9 確定)。クリップ(0〜1)は無視する(影響は表示する)。
使い方: python scripts/why_alt_won.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fit_linear import latest_probes, scored_mask  # noqa: E402
from scripts.probe import EY, EY2, LOG  # noqa: E402
from src.env import ROOT  # noqa: E402
from src.features import candidates, load  # noqa: E402

REGIONS = ["eastern-ok", "eastern-wa", "maricopa-az", "northern-ca", "south-central-tx"]
FIRE = ["fire_none", "fire_misfiled", "poi_short"]
V5 = ["comp_k14", "t_k14"] + [f"c1x_{r}" for r in REGIONS] + FIRE + ["road_undef", "rural_ur"]
ALT = ["comp_k14", "t_k14", "road_undef"] + [f"c1x_{r}" for r in REGIONS]
OBS = {"lin_v5": 0.066407806, "alt_nofac": 0.065236188}


def fitted_weights(name: str, feats: list[str], c: dict, mask: np.ndarray) -> tuple[float, np.ndarray]:
    """提出した CSV を特徴で回帰し直して重みを得る(提出時の重みそのもの。クリップされた行は除く)。"""
    p = pd.read_csv(ROOT / "submissions" / f"{name}.csv")["coverage_gap_score"].to_numpy()
    X = np.column_stack([np.ones(len(p))] + [c[f].to_numpy(float) for f in feats])
    ok = (p > 1e-9) & (p < 1 - 1e-9)
    coef, *_ = np.linalg.lstsq(X[ok], p[ok], rcond=None)
    resid = np.abs(X[ok] @ coef - p[ok]).max()
    print(f"{name}: 重みの復元の最大誤差 {resid:.1e}、クリップされた行 {int((~ok).sum())}")
    return coef[0], coef[1:]


def main() -> None:
    d = load()
    c = candidates(d)
    mask = scored_mask(d)
    pr = latest_probes(c, mask)
    feats = sorted(set(V5) | set(ALT), key=V5.index)
    a5, b5 = fitted_weights("lin_v5", V5, c, mask)
    aa, ba = fitted_weights("alt_nofac", ALT, c, mask)
    w5 = dict(zip(V5, b5))
    wa = dict(zip(ALT, ba))
    p5 = pd.read_csv(ROOT / "submissions" / "lin_v5.csv")["coverage_gap_score"].to_numpy()[mask]
    pa = pd.read_csv(ROOT / "submissions" / "alt_nofac.csv")["coverage_gap_score"].to_numpy()[mask]

    # (1) 分解。E[x y] = cov + E[x]E[y](採点される行の E[x])。c1x_eastern-wa は採点される行で 0
    rows = []
    for f in feats:
        db = w5.get(f, 0.0) - wa.get(f, 0.0)
        if f == "c1x_eastern-wa":
            exy = 0.0
        else:
            x = c[f].to_numpy(float)[mask]
            exy = pr[f]["cov"] + x.mean() * EY
        rows.append({"feature": f, "w_v5": w5.get(f, 0.0), "w_alt": wa.get(f, 0.0), "Δb": db, "E[xy]": exy,
                     "寄与 −2ΔbE[xy]": -2 * db * exy})
    t = pd.DataFrame(rows)
    pred_part = float((p5 ** 2).mean() - (pa ** 2).mean())
    cross = float(t["寄与 −2ΔbE[xy]"].sum() - 2 * (a5 - aa) * EY)
    print(t.round(5).to_string(index=False))
    print(f"\nE[p5²] − E[pa²] = {pred_part:+.6f}、切片の差の寄与 {-2 * (a5 - aa) * EY:+.6f}")
    print(f"予測される MSE の差(v5 − alt) {pred_part + cross:+.6f}  実測 {OBS['lin_v5'] ** 2 - OBS['alt_nofac'] ** 2:+.6f}")

    # (2) 集団ごとの偏り(0/1 のプローブ済みフラグ)
    print("\n集団 | 割合 | 正解の平均(プローブ) | lin_v5 | alt | P·偏り²(v5 / alt)")
    for g in ["rural_ur", "fire_none", "fire_misfiled", "fire0_rural", "fire0_prot", "ems0_fire1", "road_undef", "t_pos",
              "reg_south-central-tx", "rural_deep"]:
        if g not in pr or g not in c:
            continue
        x = c[g].to_numpy(float)[mask] > 0
        P = x.mean()
        ey = EY + pr[g]["cov"] / P if g.startswith("reg_") is False else None
        if g.startswith("reg_"):  # 縮尺つき指示関数の cov も同じ式
            ey = EY + pr[g]["cov"] / P
        for label, m in ((g, x), (f"not {g}", ~x)):
            ey_m = ey if m is x else (EY - pr[g]["cov"] / (1 - P))
            b5_, ba_ = p5[m].mean() - ey_m, pa[m].mean() - ey_m
            print(f"{label:28s} {m.mean():.3f}  {ey_m:.4f}  {p5[m].mean():.4f}  {pa[m].mean():.4f}  "
                  f"{m.mean() * b5_ ** 2:.6f} / {m.mean() * ba_ ** 2:.6f}")


if __name__ == "__main__":
    main()
