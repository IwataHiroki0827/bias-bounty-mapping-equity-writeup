"""USDA RUCA 2020 の tract 表(strata の配布物、各地域 CSV 約80KB)を取得して data/processed/ruca_all.parquet に保存する。

DuckDB の s3 読みはこの表で応答しなくなったため HTTPS で直接読む(urllib の既定 UA は 403)。
使い方: python scripts/fetch_ruca.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.remote import REGIONS  # noqa: E402

BASE = "https://data.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge/strata"


def main() -> None:
    out = []
    for r in REGIONS:
        resp = requests.get(f"{BASE}/{r}/{r}-ruca-tract-table.csv", headers={"User-Agent": "curl/8"}, timeout=60)
        resp.raise_for_status()
        d = pd.read_csv(io.StringIO(resp.text), dtype={"GEOID": str})
        d["region"] = r
        out.append(d)
    d = pd.concat(out, ignore_index=True)
    d.to_parquet(ROOT / "data" / "processed" / "ruca_all.parquet")
    print("saved", d.shape)


if __name__ == "__main__":
    main()
