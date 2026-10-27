"""writeup(Markdown)を Zindi のディスカッション投稿用 HTML に変換する。

Zindi の投稿は HTML で、<table> は使われておらず、Markdown の表(| a | b |)は記号のまま表示される(既存投稿で確認)。
そこで表は列をそろえた等幅テキスト(<pre>)にし、画像は投稿画面でアップロードする位置に目印を残す。
投稿そのものはしない(公開行為はユーザーの承認後に手で行う)。
出力: docs/post/<元のファイル名>.html
使い方: python scripts/to_zindi_post.py docs/writeup_discovery_draft.md [...]
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "post"


def width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def table_to_pre(lines: list[str]) -> str:
    rows = [[c.strip().replace("**", "") for c in ln.strip().strip("|").split("|")] for ln in lines
            if not re.fullmatch(r"\|?[\s:\-|]+\|?", ln.strip())]
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    w = [max(width(r[i]) for r in rows) for i in range(n)]
    out = []
    for j, r in enumerate(rows):
        out.append("  ".join(c + " " * (w[i] - width(c)) for i, c in enumerate(r)).rstrip())
        if j == 0:
            out.append("  ".join("-" * w[i] for i in range(n)))
    return "```\n" + "\n".join(out) + "\n```"


PRIZE = {"writeup_discovery_draft": "Best Bias Discovery", "writeup_documentation_draft": "Best Documentation"}


def convert(md: str, stem: str = "") -> str:
    md = re.sub(r"^# DRAFT — not posted\. ", "# ", md, flags=re.M)
    md = re.sub(r"^> Status:.*\n", "", md, flags=re.M)  # 下書きの状態行は投稿しない
    if stem in PRIZE:  # 他の参加者の投稿と同じく、冒頭に応募先を書く(ユーザー名は投稿時に手で入れる)
        md = re.sub(r"^(# .*\n)", rf"\1\n**Submitted for: {PRIZE[stem]}.** Zindi user: [ユーザー名を投稿時に記入]\n", md,
                    count=1, flags=re.M)
    md = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"**[画像をここにアップロード: \2 — \1]**", md)
    lines, out, buf = md.splitlines(), [], []
    for ln in lines + [""]:
        if ln.strip().startswith("|"):
            buf.append(ln)
            continue
        if buf:
            out.append(table_to_pre(buf))
            buf = []
        out.append(ln)
    return markdown.markdown("\n".join(out), extensions=["fenced_code"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in map(Path, sys.argv[1:]):
        html = convert(p.read_text(encoding="utf-8"), p.stem)
        dst = OUT / f"{p.stem}.html"
        dst.write_text(html, encoding="utf-8", newline="\n")
        print(f"{p} → {dst}  ({len(html):,} 文字、<pre> {html.count('<pre>')} 個、画像の目印 {html.count('画像をここに')} 個)")


if __name__ == "__main__":
    main()
