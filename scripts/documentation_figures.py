"""Best Documentation の図(PNG)。

fig1: プローブした特徴ごとの相関と、公開30%の抜き直しによる ±1 SD(モーメント代用の誤差)。採用 / 棄却で色分け
fig2: 結合の提出前の期待 RMSE と公開 RMSE の実測
入力: submissions/probes.jsonl, submissions/ledger.jsonl、src/features.py の候補
出力: docs/figures/doc_probe_correlations.png, docs/figures/doc_expected_vs_observed.png
使い方: python scripts/documentation_figures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.features import candidates, load  # noqa: E402
from scripts.probe import EY, EY2  # noqa: E402

OUT = ROOT / "docs" / "figures"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
USED, DROP = "#2a78d6", "#eb6834"  # 参照パレット slot 1 / 2
USED_SET = {"comp_v1", "c1x_south-central-tx", "c1x_eastern-ok", "t_k14", "fire_none", "fire_misfiled", "poi_short"}
LABEL = {"t_k14": "road estimate, k=1.4", "t_k20": "road estimate, k=2.0", "t_tiger15": "road estimate, k=1.0",
         "t_tiger30": "road, 30 m boundary ring", "t_tiger5": "road, 5 m boundary ring", "comp_v1": "composite (formula)",
         "t_tiger15_fm": "road incl. all FM roads", "c1x_eastern-ok": "composite × eastern-ok",
         "c1x_south-central-tx": "composite × south-central-tx", "fire_misfiled": "fire station misfiled",
         "poi_short": "POI shortfall", "t_bound10": "naive boundary buffer 10 m", "t_bound50": "naive boundary buffer 50 m",
         "fire_none": "no fire station place"}


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)


def subset_sd(x: np.ndarray, idx: list[np.ndarray]) -> float:
    m1, m2 = x.mean(), (x * x).mean()
    err = [((x[i] ** 2).mean() - m2) / 2 - (x[i].mean() - m1) * EY for i in idx]
    return float(np.std(err) / (np.sqrt(m2 - m1 ** 2) * np.sqrt(EY2 - EY ** 2)))


def fig_corr() -> None:
    probes = {}
    for ln in (ROOT / "submissions" / "probes.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        probes[r["name"]] = r
    c = candidates(load())
    rng = np.random.default_rng(0)
    n = len(next(iter(c.values())))
    idx = [rng.choice(n, round(n * 0.3), replace=False) for _ in range(1000)]
    rows = sorted(((k, v["corr"], subset_sd(c[k].to_numpy(float), idx)) for k, v in probes.items() if k in LABEL),
                  key=lambda t: t[1])
    fig, ax = plt.subplots(figsize=(8, 5.4), facecolor=SURFACE)
    style(ax)
    for i, (k, r, sd) in enumerate(rows):
        col = USED if k in USED_SET else DROP
        ax.plot([r - sd, r + sd], [i, i], color=col, linewidth=2, solid_capstyle="round")
        ax.plot(r, i, "o", color=col, markersize=7, markeredgecolor=SURFACE, markeredgewidth=1.5)
        ax.text(max(r + sd, 0) + 0.02, i, f"{r:+.2f}", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(range(len(rows)), [LABEL[k] for k, _, _ in rows], color=INK, fontsize=9)
    ax.axvline(0, color=GRID, linewidth=1)
    ax.set_xlim(-0.35, 0.9)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title("Correlation with the target, one public score per feature\n"
                 "(bars: ±1 SD from redrawing the 30% public split)",
                 loc="left", fontsize=10, color=INK, pad=12)
    h = [plt.Line2D([], [], color=USED, marker="o", linewidth=2), plt.Line2D([], [], color=DROP, marker="o", linewidth=2)]
    ax.legend(h, ["used in lin_v3", "not used"], loc="lower right", frameon=False, fontsize=8.5, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(OUT / "doc_probe_correlations.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


REG = ["c1x_eastern-ok", "c1x_eastern-wa", "c1x_maricopa-az", "c1x_northern-ca", "c1x_south-central-tx"]
FIRE = ["fire_none", "fire_misfiled", "poi_short"]
# (提出名, 特徴, 提出前に記録した点の期待, 提出前に登録した予測範囲 or None)
SUBMITTED = [
    ("lin4_v1", ["t_tiger15"] + FIRE, 0.06835, None),
    ("lin5_v2", ["comp_v1", "t_tiger30"] + FIRE, 0.06699, None),
    ("lin_v3", ["comp_v1", "c1x_south-central-tx", "c1x_eastern-ok", "t_k14"] + FIRE, 0.06259, None),
    ("lin_v4", ["comp_k14", "t_k14", "t_h2b05"] + REG + FIRE, 0.0596, (0.0635, 0.0644)),
    ("lin_v5", ["comp_k14", "t_k14"] + REG + FIRE + ["road_undef", "rural_ur"], 0.06146, (0.0657, 0.0667)),
]


def fig_expected() -> None:
    from scripts.fit_linear import latest_probes
    from scripts.robust_expected import robust
    led = {}
    for ln in (ROOT / "submissions" / "ledger.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        led[Path(r["file"]).stem] = r.get("public_score")
    c, probes = candidates(load()), latest_probes()
    fig, ax = plt.subplots(figsize=(7.6, 4.6), facecolor=SURFACE)
    style(ax)
    for i, (k, feats, exp, pre) in enumerate(SUBMITTED):
        obs, p90 = led[k], robust(feats, c, probes, n_sim=300)["p90"]
        if pre:  # 提出前に登録した予測範囲
            ax.add_patch(plt.Rectangle((pre[0], i - 0.22), pre[1] - pre[0], 0.44, facecolor=GRID, edgecolor="none"))
        ax.plot([exp, p90], [i, i], color=USED, linewidth=2, alpha=0.45, solid_capstyle="round")
        ax.plot(p90, i, "|", color=USED, markersize=14, markeredgewidth=2)
        ax.plot(exp, i, "o", color=USED, markersize=8, markeredgecolor=SURFACE)
        ax.plot(obs, i, "o", color=DROP, markersize=8, markeredgecolor=SURFACE)
        ax.text(max(obs, p90) + 0.0003, i, f"{obs:.4f}", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(range(len(SUBMITTED)), [f"{k} ({len(f)} features)" for k, f, _, _ in SUBMITTED], color=INK, fontsize=9)
    ax.set_xlim(0.058, 0.0745)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title("Expected RMSE before submitting vs public RMSE\n"
                 "(worse than the point expectation every time;\n"
                 "4 of 5 beyond their simulated 90th percentile)",
                 loc="left", fontsize=10, color=INK, pad=12)
    h = [plt.Line2D([], [], color=USED, marker="o", linestyle=""),
         plt.Line2D([], [], color=USED, marker="|", markersize=12, markeredgewidth=2, linestyle=""),
         plt.Rectangle((0, 0), 1, 1, facecolor=GRID),
         plt.Line2D([], [], color=DROP, marker="o", linestyle="")]
    ax.legend(h, ["expected (point)", "90th percentile (redrawn 30% split)", "range predicted before submitting",
                  "observed (public LB)"], loc="upper center", bbox_to_anchor=(0.45, -0.1),
              ncol=2, frameon=False, fontsize=8.5, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(OUT / "doc_expected_vs_observed.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig_corr()
    fig_expected()
    print("saved:", sorted(p.name for p in OUT.glob("doc_*.png")))


if __name__ == "__main__":
    main()
