#!/usr/bin/env bash
set -u
set -o pipefail

LOG_FILE="quality.txt"
STATUS=0
: > "${LOG_FILE}"
PY_TARGETS=(app.py cli.py oud tests)

{
  echo "== ruff check =="
  if command -v ruff >/dev/null 2>&1; then
    ruff check --fix "${PY_TARGETS[@]}" || STATUS=1
    ruff check "${PY_TARGETS[@]}" || STATUS=1
  else
    echo "ruff not found"
    STATUS=1
  fi
  echo
  echo "== ty check =="
  if command -v ty >/dev/null 2>&1; then
    ty check "${PY_TARGETS[@]}" || STATUS=1
  else
    echo "ty not found"
    STATUS=1
  fi
  echo
  echo "== pytest =="
  if python3 -m pytest --version >/dev/null 2>&1; then
    python3 -m pytest tests --cov --cov-fail-under=80 || STATUS=1
  else
    echo "pytest not found"
    STATUS=1
  fi
} 2>&1 | tee -a "${LOG_FILE}"

exit "${STATUS}"
