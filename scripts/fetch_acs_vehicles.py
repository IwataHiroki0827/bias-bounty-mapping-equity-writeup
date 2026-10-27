"""ACS 5年推計(2020-2024)の世帯の車保有台数(表 B08201)を tract 単位で取得する。Discovery の影響規模の算出用。

国勢調査局 API はキー必須になったため、キー不要の表別一括ファイル(www2.census.gov, 約65MB)を使う。
5州の tract だけを data/raw/ext/acs_vehicles.parquet に残し、元ファイルは消す。
B08201_E001: 世帯数、B08201_E002: 車を持たない世帯数、E008/E014/E020/E026: 1・2・3・4人以上世帯のうち車なし。
外部データは Best Bias Discovery に限り使用可。URL と取得日を data/raw/ext/acs_vehicles_sources.json に記録する。

使い方: python scripts/fetch_acs_vehicles.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402

URL = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b08201.dat"
STATES = ("04", "06", "35", "40", "48", "53")
OUT = ROOT / "data" / "raw" / "ext"
# 世帯人数別の「車なし」(1人・2人・3人・4人以上世帯)→ 人数の重み
NOVEH_BY_SIZE = {"B08201_E008": 1, "B08201_E014": 2, "B08201_E020": 3, "B08201_E026": 4}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / "acsdt5y2024-b08201.dat"
    with requests.get(URL, stream=True, timeout=300, headers={"User-Agent": "Mozilla/5.0"}) as r:
        r.raise_for_status()
        with raw.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    df = pd.read_csv(raw, sep="|", dtype=str, usecols=["GEO_ID", "B08201_E001", "B08201_E002"] + list(NOVEH_BY_SIZE))
    raw.unlink()
    tr = df[df["GEO_ID"].str.startswith("1400000US")].copy()
    tr["GEOID"] = tr["GEO_ID"].str[9:]
    tr = tr[tr["GEOID"].str[:2].isin(STATES)]
    tr = tr.rename(columns={"B08201_E001": "hh_total", "B08201_E002": "hh_no_vehicle"})
    num = ["hh_total", "hh_no_vehicle"] + list(NOVEH_BY_SIZE)
    tr[num] = tr[num].apply(pd.to_numeric, errors="coerce")
    # 列番号の取り違えを防ぐ: 世帯人数別の「車なし」の和は車なし世帯の総数(E002)と一致するはず
    gap = (tr[list(NOVEH_BY_SIZE)].sum(axis=1) - tr["hh_no_vehicle"]).abs()
    assert (gap[tr["hh_no_vehicle"].notna()] == 0).all(), f"B08201 の列が想定と違う(不一致 {int((gap > 0).sum())} tract)"
    # 車なし世帯の人数の下限: 1人・2人・3人世帯は人数どおり、4人以上は4人として数える
    tr["persons_no_vehicle_lb"] = sum(tr[c] * k for c, k in NOVEH_BY_SIZE.items())
    tr[["GEOID", "hh_total", "hh_no_vehicle", "persons_no_vehicle_lb"]].to_parquet(OUT / "acs_vehicles.parquet", index=False)
    (OUT / "acs_vehicles_sources.json").write_text(json.dumps(
        {"table": "ACS 2020-2024 5-year B08201 (table-based summary file)", "url": URL,
         "retrieved": date.today().isoformat()}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("保存:", len(tr), "tracts", "車なし世帯の合計", int(tr["hh_no_vehicle"].sum()))


if __name__ == "__main__":
    main()
