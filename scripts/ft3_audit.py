#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from oud.importers.ft3 import load_ft3
from petrucci.model import Piece

_KNOWN_VOCAL_FLAGS = 0x8000 | 0x4000 | 0x2000 | 0x1000 | 0x0100 | 0x0040 | 0x0010 | 0x0008 | 0x0004 | 0x0002


def _hex_counts(values: Counter[int]) -> dict[str, int]:
    return {f"0x{value:04x}": count for value, count in sorted(values.items())}


def audit_file(path: Path) -> dict[str, object]:
    piece = load_ft3(str(path))
    return audit_piece(piece, path=path)


def audit_piece(piece: Piece, *, path: Path) -> dict[str, object]:
    """Audit an already loaded piece without repeating FT3 parsing."""

    note_residuals: Counter[int] = Counter()
    vocal_residuals: Counter[int] = Counter()
    source_records: Counter[str] = Counter()

    for bar in piece.bars:
        for chord in bar.chords:
            note_residuals.update(
                note.ft3_extra_residual for note in chord.notes if note.ft3_extra_residual is not None
            )
        vocal_residuals.update(
            residual
            for event in bar.melody_events
            if event.accidental_flags is not None
            if (residual := event.accidental_flags & ~_KNOWN_VOCAL_FLAGS)
        )
    if piece.imported_score is not None:
        source_records.update(record.kind for record in piece.imported_score.source_records)
    unknown_records = source_records.get("unknown", 0)

    return {
        "path": str(path),
        "note_extra_residuals": _hex_counts(note_residuals),
        "vocal_flag_residuals": _hex_counts(vocal_residuals),
        "source_record_kinds": dict(sorted(source_records.items())),
        "unknown_source_records": unknown_records,
        "warnings": piece.import_warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory undecoded FT3 semantics and source records")
    parser.add_argument("path", nargs="?", default="lutemusic", help="FT3 file or directory to audit")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    source = Path(args.path)
    paths = [source] if source.is_file() else sorted(source.rglob("*.ft3"))
    reports = [audit_file(path) for path in paths]
    unresolved = [
        report
        for report in reports
        if report["note_extra_residuals"]
        or report["vocal_flag_residuals"]
        or report["unknown_source_records"]
        or report["warnings"]
    ]

    if args.json:
        print(
            json.dumps(
                {
                    "files": len(reports),
                    "unresolved_files": len(unresolved),
                    "reports": reports,
                },
                indent=2,
                sort_keys=True,
            ),
        )
    else:
        for report in reports:
            if not (
                report["note_extra_residuals"]
                or report["vocal_flag_residuals"]
                or report["unknown_source_records"]
                or report["warnings"]
            ):
                continue
            print(report["path"])
            for key in ("note_extra_residuals", "vocal_flag_residuals", "unknown_source_records", "warnings"):
                if report[key]:
                    print(f"  {key}: {report[key]}")
        print(f"Scanned {len(reports)} file(s): {len(unresolved)} with unresolved values or records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
