#!/bin/sh
# 初回セットアップ: 秘密情報ガードのフックを有効化し、.env を用意する。
# 使い方(Git Bash / WSL): sh scripts/setup.sh
set -e
cd "$(dirname "$0")/.."

git config core.hooksPath .githooks
chmod +x .githooks/pre-commit scripts/setup.sh 2>/dev/null || true
echo "pre-commit フックを有効化しました(core.hooksPath=.githooks)"

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env を作成しました。値を入れてください(git には入りません)"
else
  echo ".env は既にあります(上書きしません)"
fi

PY=$(command -v python3 || command -v python || command -v py || true)
if [ -z "$PY" ]; then
  echo "python が見つからないため check_env.py は省略しました"
  exit 0
fi
"$PY" scripts/check_env.py
