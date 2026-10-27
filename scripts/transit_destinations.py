"""Discovery: 病院・診療所・学校の名前を持つ停留所の収載率(事業者別)。

停留所名(GTFS stop_name)に施設名が入っているものを正規表現で拾い、Overture の交通地物・施設まで 100 m 以内にあるかを数える。
同じ事業者の、施設名を持たない停留所の収載率と並べる(「施設の前だけ狙って抜けている」かどうかを区別するため)。
入力: data/processed/transit_robust.parquet(scripts/discovery_transit_robust.py の出力)
出力: 標準出力の表と docs/transit_destinations.csv
使い方: python scripts/transit_destinations.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402

# 施設の種別ごとの名前の手がかり(大文字小文字は区別しない)。直後に通りの種別(Dr・Rd など)が続くものは
# 通り名(「Veterans Memorial Dr」「Medical Dr」「College St」)なので除く。
# 件数は「施設名を含む停留所」で、施設の前にあることの確認ではない(本文でもそう書く)
STREET = r"(?!\s*(?:dr|rd|st|blvd|pkwy|pky|ave|av|ln|way|ct|cir|pl|loop|trl|hwy|fwy|street|drive|road|avenue|parkway)\b)"
# 学校は小中高(K-12)だけ。University / College は通り名(University Blvd・University Pass)と区別しにくいので数えない
PATTERNS = {
    "medical": rf"\b(?:hospital|clinic|medical center|med ctr|health center|dialysis|urgent care|emergency room)(?![a-z]){STREET}",
    "school": rf"\b(?:school|elementary|elem|middle sch|high sch|academy)(?![a-z]){STREET}",
}
MIN_STOPS = 10  # 種別ごとの停留所がこれ未満の事業者は表に出さない


def main() -> None:
    s = pd.read_parquet(ROOT / "data" / "processed" / "transit_robust.parquet")
    s = s[s["GEOID"].notna()].copy()
    s["mapped"] = np.fmin(s["d_infra"], s["d_places"]) <= 100
    name = s["stop_name"].fillna("")
    for k, pat in PATTERNS.items():
        s[k] = name.str.contains(pat, case=False, regex=True)
    s["plain"] = ~(s["medical"] | s["school"])
    rows = []
    for feed, g in s.groupby("feed"):
        row = {"feed": feed, "stops": len(g), "mapped_plain": round(float(g.loc[g["plain"], "mapped"].mean()), 3)}
        for k in PATTERNS:
            gk = g[g[k]]
            row[f"{k}_stops"] = len(gk)
            row[f"{k}_missing"] = int((~gk["mapped"]).sum())
        rows.append(row)
    t = pd.DataFrame(rows).sort_values("stops", ascending=False)
    shown = t[(t["medical_stops"] >= MIN_STOPS) | (t["school_stops"] >= MIN_STOPS)]
    print(shown.to_string(index=False))
    out = ROOT / "docs" / "transit_destinations.csv"
    t.to_csv(out, index=False, encoding="utf-8", lineterminator="\n")
    print("saved:", out)
    # 例: 未収載の医療系の停留所(ヒューストンとサンアントニオ)
    for k in PATTERNS:
        ex = s[(s[k]) & (~s["mapped"]) & (s["feed"].isin(["houston_metro", "via_san_antonio"]))]
        print(f"\n未収載の {k} 系の停留所(ヒューストン・サンアントニオ、{len(ex)} 件):")
        print(ex[["feed", "stop_name", "GEOID"]].drop_duplicates("stop_name").to_string(index=False))


if __name__ == "__main__":
    main()
