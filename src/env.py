"""プロジェクト直下の .env を環境変数へ読み込む(依存ライブラリなし)。

使い方:
    from src.env import load_env, require
    load_env()
    token = require("KAGGLE_API_TOKEN")

既に設定済みの環境変数は上書きしない(シェルで一時的に差し替えた値を優先する)。
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    """`.env` を読み、未設定のキーだけ os.environ へ入れる。読み込んだキーと値を返す。"""
    if not path.exists():
        return {}
    loaded: dict[str, str] = {}
    # utf-8-sig: Windows のエディタが付ける BOM で先頭キー名が壊れるのを防ぐ
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        if not key or not value:
            continue
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded


def require(key: str) -> str:
    """必須の環境変数を返す。無ければ設定方法つきで止める。"""
    value = os.environ.get(key, "")
    if not value:
        raise SystemExit(f"{key} が未設定です。.env.example を .env にコピーして値を入れてください。")
    return value


def mask(value: str) -> str:
    """ログに出すとき用。先頭4文字だけ残す。"""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:4] + "*" * 8
