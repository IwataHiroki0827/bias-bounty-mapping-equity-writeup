"""ディスカッション全スレッドの本文とコメントを取得する(参加者のみ閲覧可)。

出力: data/raw/meta/threads/<id>.json(生データ、上書き)
      data/raw/meta/threads.txt(全文テキスト、新しい順)
使い方: python scripts/fetch_threads.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.zindi import RAW, SLUG, get, signin  # noqa: E402

OUT = RAW / "meta" / "threads"


def text(s: str | None) -> str:
    s = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</tr>|</pre>", "\n", s or "")
    s = re.sub(r"<li[^>]*>", "- ", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(s)).strip()


def who(x: dict) -> str:
    u = x.get("user") or {}
    return u.get("username", "?") if isinstance(u, dict) else "?"


def main() -> None:
    token = signin()
    threads: list[dict] = []
    for page in range(20):
        data = get(f"competitions/{SLUG}/discussions", token, page=page, per_page=50).json().get("data", [])
        if not data:
            break
        threads.extend(data)
    OUT.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for t in sorted(threads, key=lambda x: x.get("published_at") or "", reverse=True):
        tid = t["id"]
        body = get(f"discussions/{tid}", token).json().get("data", {})
        comments = get(f"discussions/{tid}/comments", token, per_page=200).json().get("data", [])
        (OUT / f"{tid}.json").write_text(json.dumps({"thread": body, "comments": comments}, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
        lines += [f"\n######## {tid} | {body.get('title')} | {who(body)} | {str(body.get('published_at'))[:10]}"
                  f" | comments={t.get('comments_count')} votes={t.get('cumulative_votes')}",
                  text(body.get("content_html") or body.get("content"))]
        for c in comments:
            lines.append(f"  -- {who(c)} ({str(c.get('created_at'))[:10]}): {text(c.get('content_html'))}")
            for rc in c.get("replies") or c.get("children") or []:
                lines.append(f"     -- {who(rc)} ({str(rc.get('created_at'))[:10]}): {text(rc.get('content_html'))}")
    (RAW / "meta" / "threads.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(threads)} threads, {sum(len(x) for x in lines)} chars")


if __name__ == "__main__":
    main()
