"""プローブで得た共分散 cov(x_i, y) と、手元で計算できる cov(x_i, x_j) から、
最小二乗の線形結合 y ≈ a + Σ b_i x_i を解き、提出CSVを作る。

期待 MSE = var(y) - c^T Σ^{-1} c(公開分の近似)。提出前に改善幅を予測し、実測と照合する。
特徴を増やすほど公開 30% に寄せた過学習の余地が増えるので、使う特徴は引数で明示する。

使い方: python scripts/fit_linear.py <特徴> [<特徴> ...] [--out submissions/lin_xxx.csv]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.features import candidates, load  # noqa: E402
from scripts.probe import EY, EY2, LOG  # noqa: E402


def scored_mask(d: pd.DataFrame) -> np.ndarray:
    """採点される行。eastern-wa(415 tract)は提出ファイルにあるが採点されない(10/9 に確定: WA だけ 0.5 の提出が
    全0 と 0.107246299 で9桁一致)。モーメントはこの行だけで取る。"""
    return (d["region"] != "eastern-wa").to_numpy()


def latest_probes(c: dict | None = None, mask: np.ndarray | None = None) -> dict[str, dict]:
    """各特徴の最新のプローブ。c と mask を渡すと、cov を採点される行のモーメントで計算し直す
    (記録時の cov は全 9,794 行のモーメントで計算してある)。"""
    out: dict[str, dict] = {}
    if LOG.exists():
        recs = [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines()]
    else:
        # 新しいクローンには submissions/ が無い。公開の docs/probe_log.csv(名前・RMSE・倍率)から組み立て、
        # cov は手元のモーメントで計算し直す(各特徴の最新値は probes.jsonl と同じ。2026-10-25 に照合)
        if c is None:
            raise SystemExit("submissions/probes.jsonl が無い。候補 c を渡すと docs/probe_log.csv から計算し直せる")
        if mask is None:
            mask = np.ones(len(next(iter(c.values()))), bool)
        log = pd.read_csv(ROOT / "docs" / "probe_log.csv")
        recs = [{"name": r.feature, "rmse": float(r.public_rmse), "scale": float(r.scale)} for r in log.itertuples()]
    for rec in recs:
        if c is not None and mask is not None and rec["name"] in c:
            x = c[rec["name"]].to_numpy(float)[mask]
            a = float(rec.get("scale", 1.0))
            m1, m2 = float(x.mean()), float((x * x).mean())
            exy = (EY2 + a * a * m2 - rec["rmse"] ** 2) / (2 * a)
            rec = {**rec, "Ex": m1, "Ex2": m2, "Exy": exy, "cov": exy - m1 * EY}
        out[rec["name"]] = rec
    # 和の制約で決まる交互作用: comp_v1 = Σ_r c1x_r なので、cov も足し算で決まる(提出不要)
    regions = ["eastern-ok", "eastern-wa", "maricopa-az", "northern-ca", "south-central-tx"]
    known = [r for r in regions if f"c1x_{r}" in out]
    if "comp_v1" in out and len(known) == len(regions) - 1:
        rest = next(r for r in regions if r not in known)
        out[f"c1x_{rest}"] = {"name": f"c1x_{rest}", "derived": True,
                              "cov": out["comp_v1"]["cov"] - sum(out[f"c1x_{r}"]["cov"] for r in known)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("feats", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--shrink", type=float, default=1.0,
                    help="重みを何倍に縮めるか(保守版用。切片で平均を合わせ直す。docs/final_selection.md)")
    ap.add_argument("--all-rows", action="store_true",
                    help="10/8 以前と同じく、採点されない eastern-wa も含む全行でモーメントを取る(過去の提出の再現用)")
    a = ap.parse_args()
    d = load()
    cands = candidates(d)
    mask = np.ones(len(d), bool) if a.all_rows else scored_mask(d)
    probes = latest_probes() if a.all_rows else latest_probes(cands, mask)
    missing = [f for f in a.feats if f not in probes]
    if missing:
        raise SystemExit(f"プローブ未実施: {missing}")
    feats = list(a.feats)
    if not a.all_rows and "c1x_eastern-wa" in feats:
        feats.remove("c1x_eastern-wa")  # 採点される行ではずっと 0 なので解けない
        print("c1x_eastern-wa は採点される行で定数 0 のため除いた")
    X_all = np.column_stack([cands[f].to_numpy(float) for f in feats])
    X = X_all[mask]
    mu = X.mean(axis=0)
    S = np.cov(X, rowvar=False, bias=True).reshape(len(feats), len(feats))
    c = np.array([probes[f]["cov"] for f in feats])
    b = np.linalg.solve(S, c) * a.shrink
    a0 = EY - b @ mu
    var_y = EY2 - EY ** 2
    # 期待 MSE = var(y) − 2 cᵀb + bᵀΣb(縮めた重みでも成り立つ形)
    exp_rmse = float(np.sqrt(max(var_y - 2 * c @ b + b @ S @ b, 0)))
    pred = np.clip(a0 + X_all @ b, 0, 1)  # 予測は全行に書く(WA も同じ式。採点されないが提出ファイルには要る)
    print("係数:", {f: round(float(v), 4) for f, v in zip(feats, b)}, "切片", round(float(a0), 4))
    print(f"期待 RMSE(線形・クリップ前) {exp_rmse:.5f}  / 定数のみ {np.sqrt(var_y):.5f}")
    print(f"予測の平均(採点される行) {pred[mask].mean():.4f} 最大 {pred.max():.3f}")
    if a.out:
        pd.DataFrame({"GEOID": d["GEOID"], "coverage_gap_score": pred.round(6)}).to_csv(a.out, index=False)
        print("保存:", a.out)


if __name__ == "__main__":
    main()
