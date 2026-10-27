"""結合の「頑健な期待 RMSE」: 公開 30% の部分集合のぶれを入れた期待値の分布。

期待 RMSE = sqrt(var(y) − 2 bᵀc + bᵀ S b) の S(特徴の共分散)と特徴の平均は、本来「公開 30% の上の値」が要るが、
どの行が公開かは分からないので全体の値で代用している。重みが打ち消し合う(符号が逆で大きい)結合ほど、
bᵀ S b が S のわずかな違いで大きく動き、期待値が楽観に偏る(10/6 の lin_v4: 期待 0.0596 → 実測 0.0668)。
ここでは公開と同じ割合の部分集合を何百回も抜き、S と平均を部分集合の値に置き換えて期待 RMSE の分布を出す。
重み b と共分散 c は固定(提出の時点で決まっている量)。

使い方: python scripts/robust_expected.py <特徴> [<特徴> ...] [--n 300]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.features import candidates, load  # noqa: E402
from scripts.fit_linear import latest_probes, scored_mask  # noqa: E402
from scripts.probe import EY, EY2  # noqa: E402


def robust(feats: list[str], c_all: dict, probes: dict, n_sim: int = 300, seed: int = 0) -> dict:
    X = np.column_stack([c_all[f].to_numpy(float) for f in feats])
    cv = np.array([probes[f]["cov"] for f in feats])
    S = np.cov(X, rowvar=False, bias=True)
    b = np.linalg.solve(S, cv)
    var_y = EY2 - EY ** 2
    point = float(np.sqrt(max(var_y - cv @ b, 0)))
    rng = np.random.default_rng(seed)
    n = len(X)
    k = round(n * 0.3)
    # プローブごとの縮尺(縮尺つきで測ったものは代用誤差が小さい)
    scale = np.array([float(probes[f].get("scale", 1.0)) for f in feats])
    m1, m2 = X.mean(axis=0), (X ** 2).mean(axis=0)
    sims, sims_s = [], []
    for _ in range(n_sim):
        idx = rng.choice(n, k, replace=False)
        # 共分散の推定誤差 e = ĉ − c_pub(モーメントを全体で代用したことによる)。式は docs/wiki-draft.md
        e = -((scale / 2) * ((X[idx] ** 2).mean(axis=0) - m2) - (X[idx].mean(axis=0) - m1) * EY)
        # 実際の公開 MSE = 期待 MSE + 2 bᵀe(重みが大きく打ち消し合うほど e が拡大される)
        Ss = np.cov(X[idx], rowvar=False, bias=True)
        # 予測の平均は全体の特徴の平均で E[y] に合わせてあるが、公開部分集合の上では b·(平均のずれ) だけずれる
        shift = float(b @ (X[idx].mean(axis=0) - m1))
        mse = var_y - 2 * (cv - e) @ b + b @ Ss @ b + shift ** 2
        sims.append(np.sqrt(max(mse, 0)))
        sims_s.append(np.sqrt(max(var_y - 2 * cv @ b + b @ Ss @ b, 0)))
    sims = np.array(sims)
    return {"point": point, "mean": float(sims.mean()), "p90": float(np.percentile(sims, 90)),
            "sd": float(sims.std()), "sd_S_only": float(np.std(sims_s)), "max_abs_w": float(np.abs(b).max())}


def main() -> None:
    args = sys.argv[1:]
    n_sim = int(args[args.index("--n") + 1]) if "--n" in args else 300
    feats = [a for a in args if not a.startswith("--") and not a.isdigit()]
    d = load()
    c_all = candidates(d)
    if "--all-rows" in args:  # 10/8 以前の計算(採点されない eastern-wa を含む)
        r = robust(feats, c_all, latest_probes(), n_sim)
    else:
        mask = scored_mask(d)
        feats = [f for f in feats if f != "c1x_eastern-wa"]
        c = {k: v[mask].reset_index(drop=True) for k, v in c_all.items()}
        r = robust(feats, c, latest_probes(c_all, mask), n_sim)
    print(f"点の期待 {r['point']:.5f} / 部分集合で: 平均 {r['mean']:.5f}・90% 点 {r['p90']:.5f}・SD {r['sd']:.5f}"
          f"(S だけのぶれ {r['sd_S_only']:.5f})/ 最大の重み {r['max_abs_w']:.3f}")


if __name__ == "__main__":
    main()
