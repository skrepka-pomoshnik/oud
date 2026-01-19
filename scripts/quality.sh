#!/usr/bin/env bash
set -u
set -o pipefail

LOG_FILE="quality.txt"
STATUS=0
: > "${LOG_FILE}"

{
  echo "== ruff check =="
  ruff check --fix . || STATUS=1
  ruff check . || STATUS=1
  echo
  echo "== ty check =="
  ty check . || STATUS=1
  echo
  echo "== pytest =="
  python3 -m pytest --cov --cov-fail-under=70 || STATUS=1
} 2>&1 | tee -a "${LOG_FILE}"

exit "${STATUS}"
