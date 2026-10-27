"""公共交通 Discovery の図(writeup 用 PNG)。

fig1: 事業者別の収載率(横棒、南中部テキサスとそれ以外で色分け、値を直接表示)
fig2: 郡ごとの「最終更新年」の分布(小さな多図、縦軸は郡内の停留所に占める割合で共通)
入力: data/processed/transit_robust.parquet, transit_history.parquet
出力: docs/figures/transit_coverage_by_agency.png, docs/figures/transit_edit_year.png
使い方: python scripts/discovery_figures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402

P = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "figures"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
TX, OTHER = "#eb6834", "#2a78d6"  # 参照パレットの slot 2 / slot 1
LABEL = {
    "tulsa_transit": "Tulsa Transit (OK)", "capmetro_austin": "Capital Metro, Austin (TX)",
    "ccrta_corpus": "Corpus Christi RTA (TX)", "ben_franklin": "Ben Franklin Transit (WA)",
    "spokane_sta": "Spokane Transit (WA)", "valley_metro": "Valley Metro, Phoenix (AZ)",
    "trax_tehama": "TRAX, Tehama County (CA)", "dart_dallas": "DART, Dallas (TX)",
    "yakima_transit": "Yakima Transit (WA)", "trinity_fortworth": "Trinity Metro, Fort Worth (TX)",
    "pfp_yakima": "People for People (WA)", "via_san_antonio": "VIA, San Antonio (TX)",
    "houston_metro": "METRO, Houston (TX)", "pahto_yakama": "Pahto, Yakama Nation (WA)",
    "sacrt_sacramento": "Sacramento RT (CA)", "roseville_transit": "Roseville Transit (CA)",
    "unitrans_davis": "Unitrans, Davis (CA)", "yuba_sutter": "Yuba-Sutter Transit (CA)",
    "placer_county": "Placer County Transit (CA)", "el_dorado": "El Dorado Transit (CA)",
    "raba_redding": "RABA, Redding (CA)", "bline_chico": "B-Line, Chico (CA)",
}


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)


def fig_coverage() -> None:
    s = pd.read_parquet(P / "transit_robust.parquet")
    s = s[s["GEOID"].notna()]
    s["m"] = np.fmin(s["d_infra"], s["d_places"]) <= 100
    g = s.groupby(["feed", "region"])["m"].agg(["size", "mean"]).reset_index().sort_values("mean")
    fig, ax = plt.subplots(figsize=(8, 5.6), facecolor=SURFACE)
    style(ax)
    colors = [TX if r == "south-central-tx" else OTHER for r in g["region"]]
    y = np.arange(len(g))
    ax.barh(y, g["mean"] * 100, height=0.62, color=colors, edgecolor=SURFACE, linewidth=2)
    for yi, (m, n) in enumerate(zip(g["mean"], g["size"])):
        ax.text(m * 100 + 1.2, yi, f"{m * 100:.1f}%  ({n:,} stops)", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(y, [LABEL[f] for f in g["feed"]], color=INK, fontsize=9)
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title("Share of each agency's GTFS stops with an Overture transit feature within 100 m",
                 loc="left", fontsize=10.5, color=INK, pad=12)
    handles = [plt.Rectangle((0, 0), 1, 1, color=TX), plt.Rectangle((0, 0), 1, 1, color=OTHER)]
    ax.legend(handles, ["South-Central Texas region", "Other regions"], loc="lower right", frameon=False,
              fontsize=8.5, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(OUT / "transit_coverage_by_agency.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def fig_edit_year() -> None:
    h = pd.read_parquet(P / "transit_history.parquet")
    s = pd.read_parquet(P / "transit_robust.parquet")
    stops = s[s["GEOID"].notna()].groupby("feed").size()
    # 郡と、その郡の主な事業者(縦軸の分母 = その事業者の GTFS 停留所数)
    panels = [("40143", "tulsa_transit", "Tulsa County", False), ("48453", "capmetro_austin", "Travis (Austin)", True),
              ("48355", "ccrta_corpus", "Nueces (Corpus Christi)", True), ("04013", "valley_metro", "Maricopa (Phoenix)", False),
              ("48029", "via_san_antonio", "Bexar (San Antonio)", True), ("48201", "houston_metro", "Harris (Houston)", True)]
    years = np.arange(2009, 2027)
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.4), sharey=True, facecolor=SURFACE)
    for ax, (county, feed, name, tx) in zip(axes.flat, panels):
        style(ax)
        by = h[h["county"] == county].groupby("yr")["n"].sum().reindex(years, fill_value=0)
        share = by / stops[feed] * 100
        ax.bar(years, share, width=0.8, color=TX if tx else OTHER, edgecolor=SURFACE, linewidth=1)
        ax.set_title(f"{name}\n{int(by.sum()):,} OSM transit features vs {int(stops[feed]):,} GTFS stops",
                     loc="left", fontsize=9, color=INK)
        ax.set_xticks([2010, 2014, 2018, 2022, 2026])
        ax.set_ylim(0, 140)
        ax.yaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
    for ax in axes[:, 0]:
        ax.set_yticks([0, 50, 100], ["0%", "50%", "100%"])
    fig.suptitle("Overture transit features by year of last OpenStreetMap edit, as % of the main agency's GTFS stops\n"
                 "Well-mapped networks were loaded in one go; Houston and San Antonio never were",
                 x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(OUT / "transit_edit_year.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig_coverage()
    fig_edit_year()
    print("saved:", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
