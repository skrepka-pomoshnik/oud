from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from scripts.corpus.midi.audit import AuditRecord, audit_corpus, load_corpus


def _default_manifests() -> list[Path]:
    root = Path("tests/fixtures/ft3/manifests")
    return sorted(root.glob("ft3-*.json"))


def _write_report(path: Path, records: list[AuditRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([asdict(record) for record in records], indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")


def _print_summary(records: list[AuditRecord]) -> None:
    statuses = Counter(record.status for record in records)
    compared = [record for record in records if record.status == "compared"]
    exact = sum(bool(record.comparison and record.comparison.exact) for record in compared)
    shifted = sum(bool(record.comparison and record.comparison.best_transposition) for record in compared)
    minimum_onset_similarity = 0.9
    weak = sum(
        bool(record.comparison and record.comparison.onset_similarity < minimum_onset_similarity) for record in compared
    )
    print(f"corpus={len(records)} compared={len(compared)} exact={exact} shifted={shifted} weak={weak}")
    print("statuses=" + ", ".join(f"{key}:{statuses[key]}" for key in sorted(statuses)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and compare companion MIDIs for the external FT3 corpus")
    parser.add_argument("manifests", nargs="*", type=Path, default=_default_manifests())
    parser.add_argument("--repo-root", type=Path, default=Path())
    parser.add_argument("--cache", type=Path, default=Path("downloads/ft3-midi"))
    parser.add_argument("--report", type=Path, default=Path("downloads/ft3-midi/report.json"))
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    try:
        records = audit_corpus(
            load_corpus(args.manifests, args.repo_root),
            args.cache,
            jobs=args.jobs,
            refresh=args.refresh,
        )
        _write_report(args.report, records)
        _print_summary(records)
        print(f"report={args.report}")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
