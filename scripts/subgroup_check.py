"""部分集団の正解平均(プローブから)と、最終2本の同じ集団の予測平均を並べる(Documentation §5)。

0/1 フラグ x の縮尺プローブから cov(x, y) が分かれば、E[y | x=1] = E[y] + cov / P(x=1)。
数千 tract の集団平均で、tract 単位の値ではない(LB からの tract 逆算はしない)。
モデルに入っているフラグでは予測平均と正解平均が構成上一致するので、照合に使うのはモデル外のフラグだけ。

使い方: python scripts/subgroup_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fit_linear import latest_probes, scored_mask  # noqa: E402
from scripts.probe import EY  # noqa: E402
from src.features import candidates, load  # noqa: E402

# eastern-wa は採点されない(10/9 確定)ので、その傾きは除き、モーメントは採点される行だけで取る
REG = [f"c1x_{r}" for r in ("eastern-ok", "maricopa-az", "northern-ca", "south-central-tx")]
MODELS = {
    "lin_v5'": ["comp_k14", "t_k14"] + REG + ["fire_none", "fire_misfiled", "poi_short", "road_undef", "rural_ur"],
    "facility-free": ["comp_k14", "t_k14", "road_undef"] + REG,
}


def predict(c: pd.DataFrame, probes: dict, feats: list[str]) -> np.ndarray:
    X = np.column_stack([c[f].to_numpy(float) for f in feats])
    S = np.cov(X, rowvar=False, bias=True)
    b = np.linalg.solve(S, np.array([probes[f]["cov"] for f in feats]))
    return np.clip(EY - b @ X.mean(0) + X @ b, 0, 1)


def main() -> None:
    d = load()
    c_all = candidates(d)
    keep = scored_mask(d)
    pr = latest_probes(c_all, keep)
    c = {k: v[keep].reset_index(drop=True) for k, v in c_all.items()}
    pred = {m: predict(c, pr, f) for m, f in MODELS.items()}

    def probed(flag: str) -> tuple[np.ndarray, float]:
        x = c[flag].to_numpy(float) > 0
        return x, EY + pr[flag]["cov"] / x.mean()

    rur, ey_rur = probed("rural_ur")
    f0r, ey_f0r = probed("fire0_rural")
    fn, ey_fn = probed("fire_none")
    groups = {
        "Rural, no fire place": (f0r, ey_f0r),
        # 差で導く: 農村全体 − 農村∧消防なし
        "Rural, fire place present": (rur & ~f0r, (ey_rur * rur.sum() - ey_f0r * f0r.sum()) / (rur & ~f0r).sum()),
        "Urban, no fire place": (fn & ~f0r, (ey_fn * fn.sum() - ey_f0r * f0r.sum()) / (fn & ~f0r).sum()),
        "No fire place, fire-protection place": probed("fire0_prot"),
        "Fire place present, no EMS place": probed("ems0_fire1"),
    }
    rows = []
    for name, (mask, ey) in groups.items():
        row = {"group": name, "share": round(mask.mean(), 3), "probed": round(ey, 4)}
        for m, p in pred.items():
            row[m] = round(p[mask].mean(), 4)
            # 集団平均のずれが MSE に足す分(集団は重なるので合計は上限の目安)
            row[f"{m} P*bias^2"] = mask.mean() * (p[mask].mean() - ey) ** 2
        rows.append(row)
    t = pd.DataFrame(rows)
    print(t.to_string(index=False, float_format=lambda v: f"{v:.5f}" if abs(v) < 0.01 else f"{v:.4f}"))
    print("\nP*bias^2 の合計(上の5集団、重なりあり):")
    for m in pred:
        print(f"  {m}: {t[f'{m} P*bias^2'].sum():.6f}")


if __name__ == "__main__":
    main()
