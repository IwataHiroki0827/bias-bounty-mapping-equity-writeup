"""最終選択(2本)の判断材料: 公開30% と非公開70% で、提出どうしの差がどれだけ入れ替わりうるかを見積もる。

正解は見えないので、y = p_ref + ε(ε は tract ごとに独立、SD = 実測 RMSE)と置き、
公開/非公開の分け方を乱数で繰り返して、2本の RMSE 差の「公開での値」と「非公開での値」のずれを測る。
ε の形(裾の重さ)は分からないので、正規と、裾の重い t 分布(自由度3)の両方で出す。
使い方: python scripts/selection_noise.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402

S = ROOT / "submissions"
# 比べる提出(公開 RMSE は ledger の実測値)
SUBS = {"lin_v3": ("lin_v3.csv", 0.067276), "lin5_v2": ("lin5_v2.csv", 0.071768),
        "lin4_v1": ("lin4_v1.csv", 0.072280), "const_0.1": ("const_0.1.csv", 0.097676)}
REF = "lin_v3"
N_SIM = 4000


def main() -> None:
    preds = {k: pd.read_csv(S / f, dtype={"GEOID": str}).set_index("GEOID")["coverage_gap_score"] for k, (f, _) in SUBS.items()}
    idx = preds[REF].index
    P = {k: v.reindex(idx).to_numpy(float) for k, v in preds.items()}
    n = len(idx)
    n_pub = round(n * 0.3)
    rng = np.random.default_rng(0)
    sd = SUBS[REF][1]
    for dist in ("normal", "t3"):
        rows = []
        for _ in range(N_SIM):
            eps = rng.standard_normal(n) if dist == "normal" else rng.standard_t(3, n) / np.sqrt(3)
            y = np.clip(P[REF] + sd * eps, 0, 1)
            pub = np.zeros(n, bool)
            pub[rng.choice(n, n_pub, replace=False)] = True
            r = {}
            for k, p in P.items():
                e2 = (p - y) ** 2
                r[k] = (np.sqrt(e2[pub].mean()), np.sqrt(e2[~pub].mean()))
            rows.append(r)
        print(f"\n== 誤差の形: {dist}(SD {sd})")
        for k in P:
            if k == REF:
                continue
            d_pub = np.array([r[k][0] - r[REF][0] for r in rows])
            d_prv = np.array([r[k][1] - r[REF][1] for r in rows])
            flip = np.mean(np.sign(d_pub) != np.sign(d_prv))
            print(f"{k:10s} vs {REF}: 公開での差 平均 {d_pub.mean():+.4f} / 公開−非公開のずれ SD {np.std(d_pub - d_prv):.4f} / "
                  f"順位が入れ替わる確率 {flip:.3f}")
        sd_pub = np.std([r[REF][0] - r[REF][1] for r in rows])
        print(f"{REF} 単体: 公開 RMSE − 非公開 RMSE の SD {sd_pub:.4f}")


if __name__ == "__main__":
    main()
