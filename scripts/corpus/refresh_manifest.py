#!/usr/bin/env python3
"""Recompute the derived metadata of corpus manifests from the payloads on disk.

A manifest entry records, next to its checksum, what the importer decodes from the file (bars, chords, staves,
notation events, lyrics). When the importer learns to decode more, those numbers change; this tool rewrites them
and reports each change so the difference can be reviewed. Entries whose payload is missing are left alone, and
only fields an entry already records are touched.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from oud.importers.ft3 import load_ft3
from petrucci import PieceAdapterError, notation_score_from_piece
from petrucci.core.model import Piece
from scripts.corpus.fetch import load_manifest, manifest_paths


def derived_fields(piece: Piece) -> dict[str, object]:
    """The manifest fields that are decoded from a payload, as ``tests/test_ft3_corpus_manifest.py`` checks them."""

    staff_kinds = Counter(staff.kind for staff in piece.imported_score.staffs) if piece.imported_score else Counter()
    try:
        score = notation_score_from_piece(piece)
    except PieceAdapterError:
        score = None
    return {
        "format": "ft3",
        "bars": len(piece.bars),
        "strings": piece.strings,
        "style": piece.style,
        "tab_chords": sum(len(bar.chords) for bar in piece.bars),
        "staff_kinds": dict(sorted(staff_kinds.items())),
        "note_staffs": len(score.staffs) if score else 0,
        "notation_events": sum(len(m.events) for staff in score.staffs for m in staff.measures) if score else 0,
        "lyrics": sum(len(staff.lyrics) for staff in score.staffs) if score else 0,
    }


def refresh(manifest_path: Path, *, write: bool) -> list[str]:
    """Update one manifest; returns one line per changed field."""

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = load_manifest(manifest_path)
    changes: list[str] = []
    for entry, path in zip(raw["files"], manifest_paths(manifest), strict=True):
        if not path.is_file():
            continue
        for field, value in derived_fields(load_ft3(str(path))).items():
            if field in entry and entry[field] != value:  # only what the manifest already records
                changes.append(f"{manifest_path.name} {entry['path']}: {field} {entry.get(field)!r} -> {value!r}")
                entry[field] = value
    if write and changes:
        manifest_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh decoded metadata in corpus manifests.")
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--write", action="store_true", help="rewrite the manifests (default: only report)")
    args = parser.parse_args(argv)
    total = 0
    for manifest_path in args.manifests:
        changes = refresh(manifest_path, write=args.write)
        total += len(changes)
        print("\n".join(changes))
    print(f"{total} field changes{'' if args.write else ' (not written; pass --write)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
