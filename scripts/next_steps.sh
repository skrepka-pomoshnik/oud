#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="next_steps.out"
{
  python3 -m pytest -q
  ruff check .
  python3 -m pytest --cov

} | tee "${LOG_FILE}"
