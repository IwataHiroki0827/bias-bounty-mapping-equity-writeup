"""`.env` の設定状況と、秘密情報ガードが有効かを確認する。値は伏せ字で表示する。

使い方: python scripts/check_env.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.env import ENV_PATH, ROOT, load_env, mask  # noqa: E402

EXAMPLE = ROOT / ".env.example"


def example_keys() -> list[str]:
    keys = []
    for line in EXAMPLE.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.append(line.split("=", 1)[0].strip())
    return keys


def git(*args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        return None


def main() -> None:
    if not ENV_PATH.exists():
        print(".env がありません。`sh scripts/setup.sh` か `cp .env.example .env` で作成してください。")
    loaded = load_env()
    for key in example_keys():
        value = loaded.get(key, "")
        print(f"  {key:<20} {'設定済み ' + mask(value) if value else '-'}")
    print()

    ignored = git("check-ignore", "-q", ".env")
    hooks = git("config", "core.hooksPath")
    if ignored is None or hooks is None:
        print("git が見つからないため、git 側の確認は省略しました")
        return
    print(".env は git 管理外:      ", "OK" if ignored.returncode == 0 else "NG(.gitignore を確認)")
    hooks_ok = hooks.stdout.strip() == ".githooks"
    print("pre-commit フック有効:   ", "OK" if hooks_ok else "NG(sh scripts/setup.sh を実行)")


if __name__ == "__main__":
    main()
