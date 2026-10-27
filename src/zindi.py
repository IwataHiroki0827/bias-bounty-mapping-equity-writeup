"""Zindi API の薄いクライアント。認証情報は .env の ZINDI_USR / ZINDI_PASSWORD。

トークン・認証情報は表示しない。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from src.env import ROOT, load_env, require

API = "https://api.zindi.world/v1"
SLUG = "bias-bounty-mapping-equity-challenge"
RAW = ROOT / "data" / "raw"


def signin() -> str:
    load_env()
    user, pw = require("ZINDI_USR"), require("ZINDI_PASSWORD")
    r = None
    for payload in ({"username": user, "password": pw}, {"email": user, "password": pw}):
        r = requests.post(f"{API}/auth/signin", data=payload, timeout=30)
        if r.status_code == 200:
            break
    if r is None or r.status_code != 200:
        raise SystemExit(f"サインイン失敗: HTTP {r.status_code if r is not None else '-'}")
    token = r.json().get("data", {}).get("auth_token", "")
    if not token:
        raise SystemExit("auth_token が取得できませんでした")
    return token


def get(path: str, token: str | None = None, **params: Any) -> requests.Response:
    if token:
        params["auth_token"] = token
    return requests.get(f"{API}/{path.lstrip('/')}", params=params, timeout=60)


def competition(token: str | None = None) -> dict[str, Any]:
    r = get(f"competitions/{SLUG}", token)
    r.raise_for_status()
    return r.json().get("data", {})


def download(name: str, token: str, dest_dir: Path = RAW) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    r = requests.get(f"{API}/competitions/{SLUG}/files/{name}", params={"auth_token": token},
                     timeout=300, stream=True)
    if r.status_code != 200:
        raise SystemExit(f"{name}: HTTP {r.status_code} — {r.text[:300]}(403なら参加/規約同意を確認)")
    with dest.open("wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 16):
            f.write(chunk)
    return dest


def save_json(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
