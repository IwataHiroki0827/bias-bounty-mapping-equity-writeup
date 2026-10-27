"""提出CSVを検証して Zindi に提出し、スコアを待って表示する。提出は ledger に記録する。

使い方:
    python scripts/submit.py <csv> --comment "説明"     # 検証→提出→スコア待ち
    python scripts/submit.py <csv> --validate-only      # 検証だけ
    python scripts/submit.py --list                     # 直近の提出一覧
提出上限は実測で 1 日 5 回(UTC 0 時リセット。規約ページの 10 回とは異なる)。
検証: SampleSubmission と同じ GEOID 集合(9,794 行)・重複なし・coverage_gap_score が 0〜1 の数値で空欄なし。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.zindi import API, RAW, SLUG, get, signin  # noqa: E402
from src.env import ROOT  # noqa: E402

SAMPLE = RAW / "src" / "SampleSubmission.csv"
LEDGER = ROOT / "submissions" / "ledger.jsonl"


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    df = pd.read_csv(path, dtype={"GEOID": str})
    ref = pd.read_csv(SAMPLE, dtype={"GEOID": str}, usecols=["GEOID"])
    if "coverage_gap_score" not in df.columns:
        return ["coverage_gap_score 列がありません"]
    if df["GEOID"].duplicated().any():
        errors.append(f"GEOID 重複 {int(df['GEOID'].duplicated().sum())} 件")
    missing, extra = set(ref["GEOID"]) - set(df["GEOID"]), set(df["GEOID"]) - set(ref["GEOID"])
    if missing or extra:
        errors.append(f"GEOID 不一致: 欠落 {len(missing)} / 余分 {len(extra)}")
    if df.isna().any().any():
        errors.append(f"空欄あり: {df.columns[df.isna().any()].tolist()}")
    s = pd.to_numeric(df["coverage_gap_score"], errors="coerce")
    if s.isna().any() or (s < 0).any() or (s > 1).any():
        errors.append("coverage_gap_score が 0〜1 の数値でない行がある")
    return errors


def list_subs(token: str, n: int = 10) -> list[dict]:
    r = get(f"competitions/{SLUG}/submissions", token, per_page=n, page=0)
    r.raise_for_status()
    return r.json().get("data", [])


def show(subs: list[dict]) -> None:
    for s in subs:
        print(f"id={s.get('id')} status={s.get('status')} public={s.get('public_score')} "
              f"created={str(s.get('created_at'))[:19]} comment={str(s.get('comment'))[:60]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--comment", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--validate-only", action="store_true")
    a = ap.parse_args()
    if a.list or not a.csv:
        show(list_subs(signin()))
        return
    path = Path(a.csv)
    errors = validate(path)
    if errors:
        raise SystemExit("[NG] 検証失敗:\n  " + "\n  ".join(errors))
    print("[OK] 検証通過(9,794 行・GEOID 一致・空欄なし・0〜1)")
    if a.validate_only:
        return
    token = signin()
    before = {s.get("id") for s in list_subs(token, 5)}
    with path.open("rb") as f:
        r = requests.post(f"{API}/competitions/{SLUG}/submissions", params={"auth_token": token},
                          data={"comment": a.comment}, files={"file": (path.name, f, "text/csv")}, timeout=120)
    if r.status_code not in (200, 201):
        raise SystemExit(f"[NG] 提出失敗 HTTP {r.status_code}: {r.text[:400]}")
    print("[SUBMIT_OK] 採点待ち…")
    sub: dict = {}
    for _ in range(36):
        time.sleep(10)
        new = [s for s in list_subs(token, 5) if s.get("id") not in before]
        if new and new[0].get("status") not in (None, "initial", "processing", "queued"):
            sub = new[0]
            break
    show([sub] if sub else list_subs(token, 3))
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "file": path.name,
           "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "comment": a.comment,
           "id": sub.get("id"), "status": sub.get("status"), "public_score": sub.get("public_score")}
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
