"""提出した結合(lin_v3・lin_v5・alt_nofac・lin_v6p)を、公開スコアの記録だけから作り直し、提出したファイルと照合する(Best Documentation の再現手順)。

入力:
  docs/probe_log.csv            各プローブの公開 RMSE(提出した集計値そのもの。tract 単位の情報は無い)。提出順に1行ずつ
  data/processed/*.parquet       特徴テーブル(scripts/build_*.py で作る。無ければ先に作る)
手順: 定数提出の較正値(E[y], E[y^2])と各プローブの RMSE から cov(x, y) を戻し、正規方程式で重みを解いて CSV を書く。
     同じ特徴を後で測り直すことがあるので、各結合は「その提出の時点までにあった行」だけを使う(N_ROWS)。
照合: 提出時に記録した SHA-256(docs/submitted_hashes.json)と、submissions/<名前>.csv があれば tract ごとの最大差。
使い方: python scripts/reproduce_submission.py [lin_v3 | lin_v5 | alt_nofac | all](既定 all)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.features import candidates, load, moments  # noqa: E402
from scripts.probe import EY, EY2, record  # noqa: E402
from scripts.fit_linear import scored_mask  # noqa: E402

LOG = ROOT / "docs" / "probe_log.csv"
REGIONS = ["eastern-ok", "eastern-wa", "maricopa-az", "northern-ca", "south-central-tx"]
FIRE = ["fire_none", "fire_misfiled", "poi_short"]
# 名前 → (特徴, 提出の時点で probe_log.csv にあった行数)。行数は submissions/ledger.jsonl の提出順から数えた
TARGETS = {
    "lin_v3": (["comp_v1", "c1x_south-central-tx", "c1x_eastern-ok", "t_k14"] + FIRE, 14),
    "lin_v5": (["comp_k14", "t_k14"] + [f"c1x_{r}" for r in REGIONS] + FIRE + ["road_undef", "rural_ur"], 23),
    # 10/7 に作り 10/9 に提出。使う特徴は 10/7〜10/8 のプローブで測り直していないので、lin_v5 と同じ 23 行で同じ値になる
    "alt_nofac": (["comp_k14", "t_k14", "road_undef"] + [f"c1x_{r}" for r in REGIONS], 23),
    # 10/10 に作り 10/11 に提出。モーメントは採点される行(eastern-wa を除く 9,379 tract)だけで取る(fit_linear の既定)
    "lin_v6p": (["comp_k14", "t_k14"] + [f"c1x_{r}" for r in REGIONS if r != "eastern-wa"]
                + FIRE + ["road_undef", "rural_ur", "fire0_rural", "fire0_prot", "t_pos", "school_short",
                          "tk14_rural", "t_ter05", "unnum_share"], 41),
}
# 10/21 に提出した最終選択の1本目。lin_v6′ + 当たり7本(= yhat_bins.py の BASE)+ 部分的な消防・郡の比・予測ビン2本・消防の建物。
# ybin2・ybin3 は yhat_bins.py の ŷ(data/processed/yhat_base.parquet)から決まる。提出は 10/21 00:02 UTC で、その時点の行は 80
_V6P = TARGETS["lin_v6p"][0]
TARGETS["lin_b2yf"] = (_V6P + ["small_core", "fire0_tribal", "ratio_over", "tk14x_south-central-tx", "tk14x_eastern-ok",
                               "tk14_x_tershare", "ruca_core", "fire_partial", "t_kcty", "ybin2", "ybin3", "fire0_bfire"], 80)
SCORED_ONLY = {"lin_v6p", "lin_b2yf"}  # 採点される行だけでモーメントを取って作った提出


def covariances(c: dict, n_rows: int, mask: np.ndarray | None = None) -> dict[str, float]:
    log = pd.read_csv(LOG).head(n_rows).drop_duplicates("feature", keep="last").set_index("feature")
    sel = (lambda x: x) if mask is None else (lambda x: x[mask])
    out = {f: record(f, log.loc[f, "public_rmse"], float(log.loc[f, "scale"]), *moments(sel(c[f])))["cov"]
           for f in log.index if f in c}
    # 和の制約: comp_v1 = Σ_r c1x_r なので、測っていない1地域の cov は足し算で決まる(scripts/fit_linear.py と同じ)
    known = [r for r in REGIONS if f"c1x_{r}" in out]
    if "comp_v1" in out and len(known) == len(REGIONS) - 1:
        rest = next(r for r in REGIONS if r not in known)
        out[f"c1x_{rest}"] = out["comp_v1"] - sum(out[f"c1x_{r}"] for r in known)
    return out


def rebuild(name: str, d: pd.DataFrame, c: dict, hashes: dict) -> bool:
    feats, n_rows = TARGETS[name]
    mask = scored_mask(d) if name in SCORED_ONLY else np.ones(len(d), bool)
    cv = covariances(c, n_rows, mask if name in SCORED_ONLY else None)
    X_all = np.column_stack([c[f].to_numpy(float) for f in feats])
    X = X_all[mask]
    cov = np.array([cv[f] for f in feats])
    S = np.cov(X, rowvar=False, bias=True)
    b = np.linalg.solve(S, cov)
    a0 = EY - b @ X.mean(axis=0)
    pred = np.clip(a0 + X_all @ b, 0, 1)
    print(f"\n### {name}(probe_log.csv の先頭 {n_rows} 行)")
    print("重み:", {f: round(float(v), 4) for f, v in zip(feats, b)}, "切片", round(float(a0), 4))
    print(f"期待 RMSE {np.sqrt(max(EY2 - EY ** 2 - cov @ b, 0)):.5f}")
    out = ROOT / "submissions" / f"{name}_repro.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"GEOID": d["GEOID"], "coverage_gap_score": pred.round(6)}).to_csv(out, index=False)
    # 新しいクローンには提出済み CSV が無いので、提出時に記録した SHA-256(改行を LF にそろえた内容)と照合する
    digest = hashlib.sha256(out.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    ok = digest == hashes[name]
    print(f"保存: {out}  SHA-256(LF) {digest[:16]}… 提出時の記録 {hashes[name][:16]}… →", "一致" if ok else "不一致")
    ref = ROOT / "submissions" / f"{name}.csv"
    if ref.exists():
        a = pd.read_csv(ref, dtype={"GEOID": str}).set_index("GEOID")["coverage_gap_score"]
        r = pd.read_csv(out, dtype={"GEOID": str}).set_index("GEOID")["coverage_gap_score"]
        print(f"提出済み {ref.name} との最大差 {float((a - r.reindex(a.index)).abs().max()):.2e}")
    return ok


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    names = list(TARGETS) if which == "all" else [which]
    d = load()
    c = candidates(d)
    hashes = json.loads((ROOT / "docs" / "submitted_hashes.json").read_text(encoding="utf-8"))
    results = {n: rebuild(n, d, c, hashes) for n in names}
    print("\n結果:", results)
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
