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

check_no_tracked_ft3() {
  local tracked
  tracked="$(git ls-files -- '*.ft3' '*.ft3.gz' '*.ft3.txt')" || return
  if [[ -n "$tracked" ]]; then
    echo "Tracked external FT3 payloads:" >&2
    echo "$tracked" >&2
    return 1
  fi
}

run_check "No tracked FT3 payloads" check_no_tracked_ft3
run_check "Architecture debt" uv run python tools/check_architecture_debt.py
run_check "Ruff" uv run ruff check .
run_check "Ruff format" uv run ruff format --check .
run_check "Ty" uv run ty check
run_check "Release artifacts" uv run python tools/check_release_artifacts.py
run_check "Pytest + coverage" uv run pytest tests --cov --cov-fail-under=85
run_check "Corpus smoke" uv run python scripts/corpus_smoke.py lutemusic

exit "$STATUS"
