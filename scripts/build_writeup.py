"""提出用の writeup を1本にまとめる: Documentation の短縮版の後ろに、見出しを付けた Best Bias Discovery の節(短縮版)を置く。

規約は「Discovery は writeup の中に、はっきり見出しを付けた節を設ける」なので、2本を1本にし、各版の見出しを1段下げる。
出力: docs/writeup.md(下書きの印と状態行は外す)
使い方: python scripts/build_writeup.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO = "https://github.com/IwataHiroki0827/bias-bounty-mapping-equity-writeup"
FINAL = [("lin_b2yf", "mMfxzUkA", "0.062055"), ("alt_nofac", "GH4efdZH", "0.065236")]


def part(name: str, label: str) -> str:
    md = (DOCS / name).read_text(encoding="utf-8").replace("\r\n", "\n")
    md = re.sub(r"^> Status:.*\n", "", md, flags=re.M)
    out, fenced = [], False
    for ln in md.splitlines():
        if ln.startswith("```"):
            fenced = not fenced
        elif not fenced and ln.startswith("#"):
            if ln.startswith("# "):  # 表題 → 部の見出し
                ln = f"## {label}: " + re.sub(r"^# (DRAFT — not posted\. )?(Best [A-Za-z ]+: )?", "", ln)
            else:
                ln = "#" + ln
        out.append(ln)
    return "\n".join(out).strip() + "\n"


def main() -> None:
    picks = "; ".join(f"{n} (submission {i}, public RMSE {s})" for n, i, s in FINAL)
    head = (
        "# Bias Bounty: Mapping Equity Challenge — methodology write-up\n\n"
        "**Submitted for: Best Documentation and Best Bias Discovery.** Zindi username: as entered on the submission form.\n\n"
        f"**Leaderboard submissions this write-up describes:** the two final picks, {picks}. The Best Bias Discovery part "
        "(Part B) uses no leaderboard submission and calibrates none.\n\n"
        f"**Code and full records:** {REPO} (one command per part reproduces every number; see A §8 and B "
        "\"Reproducibility\"). The longer versions of both parts are in the repository "
        "(`docs/writeup_documentation_draft.md`, `docs/writeup_discovery_draft.md`).\n\n"
        "- **Part A — Best Documentation:** estimating the coverage gap after the reference layers were withdrawn.\n"
        "- **Part B — Best Bias Discovery:** whether a bus stop is on the open map depends on which agency runs the bus.\n"
    )
    body = "\n".join([head, part("writeup_documentation_short.md", "Part A — Best Documentation"),
                      part("writeup_discovery_short.md", "Part B — Best Bias Discovery")])
    dst = DOCS / "writeup.md"
    dst.write_bytes(body.encode("utf-8"))
    print(f"{dst}  ({len(body):,} 文字、見出し {len(re.findall(r'^#', body, flags=re.M))} 個)")


if __name__ == "__main__":
    main()
