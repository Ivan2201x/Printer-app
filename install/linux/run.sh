#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source "$ROOT/venv/bin/activate"
exec python main.py
