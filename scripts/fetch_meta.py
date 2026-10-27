"""コンペのメタ情報(概要・ルール・評価・データ説明・ファイル一覧)を data/raw/meta/ に保存する。

使い方: python scripts/fetch_meta.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.zindi import RAW, SLUG, competition, get, save_json, signin  # noqa: E402

META = RAW / "meta"


def main() -> None:
    token = signin()
    print("[OK] サインイン")
    comp = competition(token)
    save_json(comp, META / "competition.json")
    print("keys:", sorted(comp.keys()))
    # ページ類(存在すれば)
    for sub in ("pages", "discussions", "leaderboard", "participations"):
        r = get(f"competitions/{SLUG}/{sub}", token)
        print(f"{sub}: HTTP {r.status_code}")
        if r.ok:
            save_json(r.json(), META / f"{sub}.json")


if __name__ == "__main__":
    main()
