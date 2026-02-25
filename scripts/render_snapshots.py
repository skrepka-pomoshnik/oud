#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_repo_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    root_str = str(repo_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check/update synthetic ASCII render snapshots")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rewrite snapshot fixtures from current renderer output",
    )
    args = parser.parse_args()

    _ensure_repo_on_path()
    from tests.render_snapshot_utils import (  # noqa: PLC0415
        snapshot_cases,
        snapshot_mismatch_report,
        write_snapshot_fixtures,
    )

    if args.update:
        write_snapshot_fixtures()
        print("Updated render snapshot fixtures.")
        return 0

    mismatches: list[str] = []
    for case in snapshot_cases():
        report = snapshot_mismatch_report(case)
        if report:
            mismatches.append(report)
    if mismatches:
        print("\n\n".join(mismatches))
        print(
            "\nRun `./.venv/bin/python scripts/render_snapshots.py --update` "
            "to refresh fixtures.",
        )
        return 1
    print("All render snapshots match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
