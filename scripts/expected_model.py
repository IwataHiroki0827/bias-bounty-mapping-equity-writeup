"""採点式の構造を持つ期待値モデル ŷ_E(Fable 10/14 の提案)。パラメータは提出せず、手元のプローブの共分散に一致させて解く。

構造(data_README の採点式): 合成 = 定義された成分(道路・建物・施設)の平均。各成分は 1 − min(1, Overture / 参照)。
- 道路: 参照 R = k_r · proxy · e^ε, ε ~ N(0, σ²)。u = log(O / (k_r·proxy)) とおくと
  E[gap] = (1 − Φ(u/σ)) − e^{u+σ²/2} (1 − Φ((u+σ²)/σ))。σ = σ_r · e^{γ·ruca_core}。
  proxy = 0 の tract は確率 π で定義され、そのときのギャップは g0。
- 建物: Overture に1棟以上あれば定義、ギャップ b0(小さい定数)。
- 施設: HIFLD 半分 = 定義された種別(消防・学校)の平均、CBP 半分 = α · poi_short_cty(places があれば定義)。
  消防: 署あり → E[K/(O+K)], K ~ Poisson(u_f·λ)(λ は features.fire_partial と同じ回帰)。
        署なし・名前で消防と分かる施設あり → 1。どちらもなし → 確率 q(rural・部族・人口のロジスティック)で定義・ギャップ 1。
  学校: カテゴリあり → 0、名前だけ → 1、どちらもなし → 未定義。
- 道路の定義 × 消防の定義の4通りを列挙して期待値を取る。

当てはめ: 予測 ŷ_E の、プローブ済みの各特徴との共分散(採点行のモーメント)が、LB から逆算した共分散に一致するように
θ を最小二乗で解く(相関の単位で残差を取る)。E[ŷ_E] = E[y] も制約に入れる。
ŷ_E の射影が線形の最良予測と一致するので、ŷ_E が新しく持つのは「線形で表せない部分」だけ。その価値はプローブ1本(ŷ_E@1)で測る。

使い方: python scripts/expected_model.py [--write]   (--write で submissions/probe 用の特徴 data/processed/yhat_e.parquet を書く)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy.special import expit
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fit_linear import latest_probes, scored_mask  # noqa: E402
from scripts.probe import EY, EY2  # noqa: E402
from src.env import ROOT  # noqa: E402
from src.features import candidates, load  # noqa: E402

REG = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]
NAMES = ([f"logk_{r}" for r in REG] + [f"logsig_{r}" for r in REG]
         + ["gam_core", "logit_pi", "logit_g0", "logit_b0", "log_uf", "q0", "q_rur", "q_trib", "q_lpop", "logit_alpha"])
X0 = np.array([np.log(1.4)] * 4 + [np.log(0.5)] * 4 + [0.0, 0.0, 0.0, -5.0, np.log(0.45), 0.0, 1.0, 0.5, 0.0, 0.0])


def road_gap(o: np.ndarray, ref: np.ndarray, sig: np.ndarray) -> np.ndarray:
    """E[1 − min(1, o/R)], log R ~ N(log ref, sig²)。ref > 0 の行だけで使う。"""
    with np.errstate(divide="ignore"):
        u = np.log(np.where(o > 0, o, 1e-12) / ref)
    a = 1 - norm.cdf(u / sig)
    b = np.exp(np.clip(u + sig ** 2 / 2, -50, 50)) * (1 - norm.cdf((u + sig ** 2) / sig))
    return np.clip(np.where(o > 0, a - b, 1.0), 0, 1)


class Model:
    def __init__(self, d: pd.DataFrame, c: dict) -> None:
        self.o = d["tg_ov_hw_km"].to_numpy(float)
        self.proxy = (d["tg_num_in_mult_km"] + d["tg_num_ring15_km"]).to_numpy(float)
        self.reg = d["region"].to_numpy()
        self.core = c["ruca_core"].to_numpy(float)
        self.has_bldg = (d["bldg_n"] > 0).to_numpy()
        pop = d["pop_total"].fillna(0).to_numpy(float)
        self.rur = (d["ur_class"] == "Rural").to_numpy(float)
        self.trib = d["tribal_any"].fillna(False).astype(bool).to_numpy(float) if "tribal_any" in d else np.zeros(len(d))
        self.lpop = (np.log1p(pop) - np.log1p(pop).mean()) / np.log1p(pop).std()
        fo = d["pp_fire_cat_n"].fillna(0).to_numpy(float)
        self.fire_o = fo
        self.fire_mis = (d["pp_fire_misfiled_n"].fillna(0) > 0).to_numpy()
        # λ: features.fire_partial と同じ回帰を逆算せずに再計算(k/(o+k) から k を戻す)
        fp = c["fire_partial"].to_numpy(float)
        self.lam045 = np.where(fo > 0, fp * fo / np.clip(1 - fp, 1e-9, None), 0.0)  # = 0.45·λ
        sc, sm = d["pp_school_cat_n"].fillna(0).to_numpy(), d["pp_school_misfiled_n"].fillna(0).to_numpy()
        self.school = np.where(sc > 0, 0.0, np.where(sm > 0, 1.0, np.nan))
        self.has_poi = (d["pp_poi_all_n"].fillna(0) > 0).to_numpy()
        self.cbp_x = c["poi_short_cty"].to_numpy(float)

    def predict(self, th: np.ndarray) -> np.ndarray:
        p = dict(zip(NAMES, th))
        n = len(self.o)
        k = np.ones(n) * 1.4
        sig = np.ones(n) * 0.5
        for r in REG:
            m = self.reg == r
            k[m] = np.exp(p[f"logk_{r}"])
            sig[m] = np.exp(p[f"logsig_{r}"])
        sig = sig * np.exp(p["gam_core"] * self.core)
        pos = self.proxy > 0
        t_def_gap = np.zeros(n)
        t_def_gap[pos] = road_gap(self.o[pos], k[pos] * self.proxy[pos], sig[pos])
        t_def_gap[~pos] = expit(p["logit_g0"])
        t_pdef = np.where(pos, 1.0, expit(p["logit_pi"]))
        b0 = expit(p["logit_b0"])
        # 消防
        uf = np.exp(p["log_uf"]) / 0.45
        kk = uf * self.lam045
        fire_gap_present = np.where(self.fire_o > 0, kk / (self.fire_o + kk + 1e-12), np.nan)
        q = expit(p["q0"] + p["q_rur"] * self.rur + p["q_trib"] * self.trib + p["q_lpop"] * self.lpop)
        f_pdef = np.where(self.fire_o > 0, 1.0, np.where(self.fire_mis, 1.0, q))
        f_gap = np.where(self.fire_o > 0, fire_gap_present, 1.0)
        cbp = np.clip(expit(p["logit_alpha"]) * 2 * self.cbp_x, 0, 1)
        out = np.zeros(n)
        for t_def in (True, False):
            pt = t_pdef if t_def else 1 - t_pdef
            for f_def in (True, False):
                pf = f_pdef if f_def else 1 - f_pdef
                fire = np.where(f_def, f_gap, np.nan)
                hif = np.nanmean(np.vstack([fire, self.school]), axis=0)
                hif_def = ~np.isnan(hif)
                cb = np.where(self.has_poi, cbp, np.nan)
                poi = np.nanmean(np.vstack([np.where(hif_def, hif, np.nan), cb]), axis=0)
                comps = np.vstack([np.where(t_def, t_def_gap, np.nan),
                                   np.where(self.has_bldg, b0, np.nan), poi])
                val = np.nan_to_num(np.nanmean(comps, axis=0), nan=0.0)
                out += pt * pf * val
        return out


def main() -> None:
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)  # 全 NaN 行の nanmean
    d = load()
    c = candidates(d)
    mask = scored_mask(d)
    p = latest_probes(c, mask)
    # 採点行で定数の特徴(東WA だけの特徴など)は除く
    feats = [f for f in p if f in c and not p[f].get("derived") and c[f].to_numpy(float)[mask].std() > 0
             and f != "yhat_e"]  # 自分自身のプローブは当てはめに使わない
    sd_y = np.sqrt(EY2 - EY ** 2)
    X = np.column_stack([c[f].to_numpy(float)[mask] for f in feats])
    Xc = X - X.mean(0)
    sdx = X.std(0)
    target = np.array([p[f]["cov"] for f in feats])
    m = Model(d, c)

    def resid(th):
        y = m.predict(th)[mask]
        cov = (Xc * (y - y.mean())[:, None]).mean(0)
        r = (cov - target) / (sdx * sd_y)
        return np.append(r, 5 * (y.mean() - EY) / sd_y)

    sol = least_squares(resid, X0, method="trf", max_nfev=400)
    y = m.predict(sol.x)
    r = resid(sol.x)
    print(f"当てはめ: 残差 RMS(相関の単位) {np.sqrt(np.mean(r[:-1] ** 2)):.4f}  E[ŷ]={y[mask].mean():.4f}(E[y]={EY:.4f})  特徴 {len(feats)} 本")
    for nm, v in zip(NAMES, sol.x):
        print(f"  {nm:22s} {v:+.3f}")
    # 線形の最良予測との関係: ŷ_E を特徴の span に射影した残り(新しい情報になりうる部分)の大きさ
    coef, *_ = np.linalg.lstsq(Xc, y[mask] - y[mask].mean(), rcond=None)
    orth = y[mask] - y[mask].mean() - Xc @ coef
    print(f"ŷ_E の SD {y[mask].std():.4f}、特徴の span に対する直交成分の SD {orth.std():.4f}(割合 {orth.var() / y[mask].var():.3f})")
    worst = np.argsort(-np.abs(r[:-1]))[:8]
    print("当てはまりの悪い特徴:", ", ".join(f"{feats[i]} {r[i]:+.3f}" for i in worst))
    if "--write" in sys.argv:
        out = ROOT / "data" / "processed" / "yhat_e.parquet"
        pd.DataFrame({"GEOID": d["GEOID"], "yhat_e": np.clip(y, 0, 1)}).to_parquet(out, index=False)
        print("書き出し:", out)


if __name__ == "__main__":
    main()
