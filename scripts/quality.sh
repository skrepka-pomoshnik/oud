#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"
export UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"
STATUS=0

command -v uv >/dev/null 2>&1 || { echo "ERROR: uv is required" >&2; exit 127; }

run_check() {
  local label="$1"
  shift
  echo "== $label =="
  if "$@"; then
    echo "[ok] $label"
  else
    local exit_code=$?
    echo "[fail:$exit_code] $label" >&2
    STATUS=1
  fi
  echo
}

run_check "Ruff" uv run ruff check .
run_check "Ruff format" uv run ruff format --check .
run_check "Ty" uv run ty check oud tests
run_check "Pytest + coverage" uv run pytest tests --cov --cov-fail-under=80
run_check "Corpus smoke" uv run python scripts/corpus_smoke.py lutemusic

exit "$STATUS"
