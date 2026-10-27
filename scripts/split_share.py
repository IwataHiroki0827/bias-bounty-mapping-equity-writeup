"""公開 30% の分け方の検証: 地域の 0/1 指標を縮尺 2 種で出した公開スコアから、公開部分に占めるその地域の割合を解く。

a·1_r を出すと RMSE² = E_pub[y²] − 2a·E_pub[y·1_r] + a²·E_pub[1_r]。E_pub[y²] は定数提出で既知なので、
縮尺 a1・a2 の 2 本で未知数 2 つ(E_pub[y·1_r] と E_pub[1_r])が解ける。E_pub[1_r] が全体の割合に近ければ、
少なくとも地域の単位では無作為に分けられている。求めるのは集計値だけで、tract 単位の情報は出ない。
使い方: python scripts/split_share.py reg_south-central-tx
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.features import candidates, load  # noqa: E402
from scripts.probe import EY, EY2, LOG  # noqa: E402


def main() -> None:
    name = sys.argv[1]
    recs = [json.loads(ln) for ln in LOG.read_text(encoding="utf-8").splitlines()]
    pts = {(r.get("scale", 1.0)): r["rmse"] for r in recs if r["name"] == name}
    if len(pts) < 2:
        raise SystemExit(f"{name} の縮尺違いのプローブが2本必要(今 {sorted(pts)})")
    (a1, r1), (a2, r2) = sorted(pts.items())[:2]
    # r² = EY2 − 2a·A + a²·B  →  連立方程式
    M = np.array([[-2 * a1, a1 ** 2], [-2 * a2, a2 ** 2]])
    v = np.array([r1 ** 2 - EY2, r2 ** 2 - EY2])
    A, B = np.linalg.solve(M, v)
    full = float(candidates(load())[name].mean())
    print(f"{name}: 公開部分の割合 E_pub[1_r] = {B:.4f}(全体 {full:.4f})/ 公開部分での y の平均(その地域)= {A / B:.4f}")


if __name__ == "__main__":
    main()
