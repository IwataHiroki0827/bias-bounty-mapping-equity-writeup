"""公開リーダーボード(participations)を全件取得し、スコア分布と自分の順位を表示する。

使い方: python scripts/leaderboard.py [--top 20]
保存先: data/raw/meta/leaderboard_<日時>.json(直近10件だけ残す)
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.zindi import RAW, SLUG, get, save_json, signin  # noqa: E402

KEEP = 10


def fetch_all(token: str) -> list[dict]:
    rows: list[dict] = []
    for page in range(100):
        r = get(f"competitions/{SLUG}/participations", token, per_page=100, page=page)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            break
        rows.extend(data)
    return rows


def owner(x: dict) -> str:
    u = x.get("user")
    return u.get("username", "") if isinstance(u, dict) else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()
    token = signin()
    rows = fetch_all(token)
    out_dir = RAW / "meta"
    save_json(rows, out_dir / f"leaderboard_{datetime.now():%Y%m%d_%H%M}.json")
    for old in sorted(out_dir.glob("leaderboard_*.json"))[:-KEEP]:
        old.unlink()

    ranked = sorted((x for x in rows if x.get("best_public_score") is not None),
                    key=lambda x: x.get("public_rank") or 1e9)
    print(f"参加 {len(rows)} / スコアあり {len(ranked)}")
    buckets = Counter()
    for x in ranked:
        s = float(x["best_public_score"])
        b = "0.0" if s == 0 else "<1e-4" if s < 1e-4 else "<1e-3" if s < 1e-3 else "<0.01" if s < 0.01 else "<0.05" if s < 0.05 else "<0.1" if s < 0.1 else ">=0.1"
        buckets[b] += 1
    for b in ("0.0", "<1e-4", "<1e-3", "<0.01", "<0.05", "<0.1", ">=0.1"):
        print(f"  {b:>6}: {buckets[b]}")
    for x in ranked[: args.top]:
        print(f"#{x.get('public_rank')}: {x['best_public_score']} 提出{x.get('submission_count')} 最良提出 {str(x.get('best_public_submitted_at'))[:16]}")
    me = os.environ.get("ZINDI_USR", "")
    mine = [x for x in rows if me and owner(x) == me]
    print("自分:", f"rank={mine[0].get('public_rank')} best={mine[0].get('best_public_score')}" if mine else "未参加/未提出")


if __name__ == "__main__":
    main()
