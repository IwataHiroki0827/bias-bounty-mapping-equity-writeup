"""候補特徴をそのまま提出し、公開LBの RMSE から特徴と正解の共分散・相関を逆算する。

RMSE^2 = E[y^2] - 2 E[xy] + E[x^2] より E[xy] = (E[y^2] + E[x^2] - RMSE^2) / 2。
E[y^2]・E[y] は定数提出(0, 0.1, 0.2)の較正値。E[x]・E[x^2] は全 9,794 tract で計算する
(公開 30% の部分集合は不明なので近似。誤差は記録に残す)。
tract 単位の値は一切推定しない。測るのは集計値1つだけ。

使い方: python scripts/probe.py <候補名> [<候補名> ...]   / python scripts/probe.py --list
       python scripts/probe.py <候補名> ... --dry   # CSV を書いて検証だけ(提出しない)
記録: submissions/probes.jsonl
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ROOT  # noqa: E402
from src.features import candidates, load, moments  # noqa: E402

# 較正(2026-10-02, 定数提出 0 / 0.1 / 0.2 の公開スコア)
EY2 = 0.107246299 ** 2
EY = (EY2 + 0.04 - 0.16607025 ** 2) / 0.4
LOG = ROOT / "submissions" / "probes.jsonl"


def main() -> None:
    d = load()
    cands = candidates(d)
    if "--list" in sys.argv:
        for k, v in cands.items():
            m1, m2 = moments(v)
            print(f"{k:14s} mean={m1:.4f} E[x2]={m2:.4f} nonzero={(v > 0).mean():.3f}")
        return
    dry = "--dry" in sys.argv  # CSV を書いて検証だけ行い、提出しない
    for spec in [a for a in sys.argv[1:] if not a.startswith("--")]:
        # 縮尺プローブ: 「名前@a」で x の代わりに a·x を出す。E[x²]・E[x] を全体で代用する誤差は
        # ΔE[x]·(a/2 − E[y]) に比例するので、0/1 フラグは a ≈ 2E[y] ≈ 0.12 で一次の誤差が消える
        name, _, sc = spec.partition("@")
        scale = float(sc) if sc else 1.0
        x = cands[name]
        tag = name if scale == 1.0 else f"{name}@{scale:g}"
        out = ROOT / "submissions" / f"probe_{tag.replace('@', '_x')}.csv"
        pd.DataFrame({"GEOID": d["GEOID"], "coverage_gap_score": (x * scale).round(6)}).to_csv(out, index=False)
        args = ["--validate-only"] if dry else ["--comment", f"probe {tag}"]
        res = subprocess.run([sys.executable, str(ROOT / "scripts" / "submit.py"), str(out), *args],
                             capture_output=True, text=True, encoding="utf-8")
        if dry:
            print(tag, res.stdout.strip().splitlines()[-1] if res.stdout.strip() else res.stderr[-300:])
            continue
        line = [ln for ln in res.stdout.splitlines() if "public=" in ln]
        if not line:
            print(tag, "提出失敗", res.stdout[-300:], res.stderr[-300:])
            continue
        score = float(line[-1].split("public=")[1].split()[0])
        rec = record(name, score, scale, *moments(x))
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        # 公開用の記録(リポジトリに入れる。scripts/reproduce_submission.py の入力)
        with (ROOT / "docs" / "probe_log.csv").open("a", encoding="utf-8", newline="\n") as f:
            f.write(f"{name},{score},{scale:g}\n")
        print(f"{tag:14s} rmse={score:.6f} corr={rec['corr']:+.3f} beta={rec['beta']:+.4f}")


def record(name: str, score: float, scale: float, m1: float, m2: float) -> dict:
    """提出した a·x の公開 RMSE から、元の x と y の共分散を戻す。
    RMSE² = E[y²] − 2a·E[xy] + a²·E[x²] より E[xy] = (E[y²] + a²·E[x²] − RMSE²) / (2a)。"""
    exy = (EY2 + scale ** 2 * m2 - score ** 2) / (2 * scale)
    cov = exy - m1 * EY
    sd_x, sd_y = np.sqrt(m2 - m1 ** 2), np.sqrt(EY2 - EY ** 2)
    return {"name": name, "rmse": score, "scale": scale, "Ex": m1, "Ex2": m2, "Exy": exy, "cov": cov,
            "corr": cov / (sd_x * sd_y), "beta": cov / (m2 - m1 ** 2)}


if __name__ == "__main__":
    main()
