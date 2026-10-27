"""公共交通 Discovery の数量化: 停留所が地図に載るかを「事業者」と「必要度(車なし世帯・SVI・都市/農村・部族)」の
どちらがどれだけ説明するかを、停留所単位のロジスティック回帰で比べる。

入力: data/processed/transit_robust.parquet(停留所と最近傍距離)、transit_tracts.parquet(tract の車なし世帯比率)
mapped = Overture infrastructure / places のどちらかが 100m 以内(writeup と同じ定義)。
指標: McFadden 擬似R²(切片のみモデル比)と、モデル間の尤度比検定。事業者内の効果は事業者ダミーを入れた上での係数。
使い方: python scripts/discovery_transit_model.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402

P = ROOT / "data" / "processed"
RADIUS_M = 100.0


def load() -> pd.DataFrame:
    s = pd.read_parquet(P / "transit_robust.parquet")
    t = pd.read_parquet(P / "transit_tracts.parquet")[["feed", "GEOID", "noveh_share"]]
    s = s.merge(t, on=["feed", "GEOID"], how="left")
    s["mapped"] = (np.fmin(s["d_infra"], s["d_places"]) <= RADIUS_M).astype(int)
    s["rural"] = (s["ur_class"] == "Rural").astype(float)
    s["tribal"] = s["tribal_any"].astype(str).str.lower().eq("true").astype(float)
    return s.dropna(subset=["svi_overall", "noveh_share"])


def fit(X: pd.DataFrame, y: np.ndarray) -> tuple[float, LogisticRegression]:
    """ほぼ無正則化のロジスティック回帰。対数尤度(合計)を返す。"""
    m = LogisticRegression(C=1e6, max_iter=5000)
    m.fit(X, y)
    p = m.predict_proba(X)[:, 1]
    return -log_loss(y, p, normalize=False), m


def main() -> None:
    s = load()
    y = s["mapped"].to_numpy()
    need = s[["noveh_share", "svi_overall", "rural", "tribal"]]
    agency = pd.get_dummies(s["feed"], drop_first=True, dtype=float)
    ll0 = float(np.sum(y * np.log(y.mean()) + (1 - y) * np.log(1 - y.mean())))
    rows = []
    for name, X in (("need only", need), ("agency only", agency), ("agency + need", pd.concat([agency, need], axis=1))):
        ll, m = fit(X, y)
        rows.append({"model": name, "k": X.shape[1], "loglik": round(ll, 1), "McFadden R2": round(1 - ll / ll0, 3),
                     "AUC": round(roc_auc_score(y, m.predict_proba(X)[:, 1]), 3)})
        if name == "agency + need":
            coef = dict(zip(X.columns, m.coef_[0]))
    out = pd.DataFrame(rows)
    print(f"stops {len(s):,} / mapped {y.mean():.3f} / agencies {s['feed'].nunique()}")
    print(out.to_string(index=False))
    ll = dict(zip(out["model"], out["loglik"]))
    for base, add, df in (("agency only", "need", need.shape[1]), ("need only", "agency", agency.shape[1])):
        lr = 2 * (ll["agency + need"] - ll[base])
        print(f"adding {add} to {base}: LR = {lr:.1f}, df = {df}, p = {stats.chi2.sf(lr, df):.2g}")
    print("need coefficients within agency (log-odds):",
          {k: round(float(coef[k]), 3) for k in need.columns})
    # 事業者内の車なし世帯比率と載る率(tract 単位、停留所5以上)
    tr = s.groupby(["feed", "GEOID"]).agg(n=("mapped", "size"), mapped=("mapped", "mean"), noveh=("noveh_share", "first"))
    tr = tr[tr["n"] >= 5].reset_index()
    res = []
    for f, g in tr.groupby("feed"):
        if len(g) >= 10:
            r = stats.spearmanr(g["noveh"], g["mapped"])
            res.append((f, len(g), r.statistic, r.pvalue))
    # 事業者ごとに検定を繰り返すので、Benjamini-Hochberg で多重比較を補正した q 値も出す
    q = stats.false_discovery_control([p for *_, p in res], method="bh")
    for (f, n, rho, p), qq in zip(res, q):
        print(f"  {f:28s} tracts {n:4d}  spearman(no-car share, mapped) = {rho:+.2f} (p = {p:.2g}, BH q = {qq:.2g})")
    print(f"BH q < 0.05 の事業者: {sum(qq < 0.05 for qq in q)} / {len(q)}")


if __name__ == "__main__":
    main()
