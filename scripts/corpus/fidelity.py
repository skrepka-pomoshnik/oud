#!/usr/bin/env python3
"""Compare what Oud decodes from each corpus FT3 with the layout of its reference PDF.

Both inputs are local and untracked. For every manifest entry that has its FT3 and its PDF, the script reports the
bar count Oud reads against the bar count counted on the typeset page, with the page and system structure of the
PDF. It measures decoding and layout agreement, not pixel identity.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from oud.importers.ft3 import load_ft3
from scripts.corpus.fetch import load_manifest, manifest_paths
from scripts.corpus.pdf_structure import PageShape, PdfStructureError, analyse_pdf
from scripts.corpus.pdfs import local_name

DEFAULT_PDFS = Path("downloads/gerbode/pdf")
TAB_ONLY_LINES = 6


@dataclass(frozen=True)
class FileResult:
    name: str
    oud_bars: int | None
    pdf_bars: int | None
    pages: int
    systems: int
    line_counts: tuple[int, ...]
    error: str | None = None

    @property
    def agrees(self) -> bool:
        return self.oud_bars is not None and self.oud_bars == self.pdf_bars


def _pdf_summary(pages: list[PageShape]) -> tuple[int, int, tuple[int, ...]]:
    """Bars and systems of the tablature staves (six or more lines); notation staves have four or five."""

    staves = [system for page in pages for system in page.systems]
    tab = [system for system in staves if system.lines >= TAB_ONLY_LINES]
    return sum(system.bars for system in tab), len(tab), tuple(sorted({system.lines for system in staves}))


def compare_entry(ft3: Path, pdf: Path, name: str) -> FileResult:
    try:
        oud_bars: int | None = len(load_ft3(str(ft3)).bars)
    except (OSError, ValueError) as exc:
        return FileResult(name, None, None, 0, 0, (), f"ft3: {exc}")
    try:
        pages = analyse_pdf(pdf)
    except PdfStructureError as exc:
        return FileResult(name, oud_bars, None, 0, 0, (), f"pdf: {exc}")
    pdf_bars, systems, line_counts = _pdf_summary(pages)
    return FileResult(name, oud_bars, pdf_bars, len(pages), systems, line_counts)


def collect(manifests: list[Path], pdf_dir: Path, *, limit: int) -> list[FileResult]:
    results: list[FileResult] = []
    for manifest_path in manifests:
        manifest = load_manifest(manifest_path)
        for entry, ft3 in zip(manifest.files, manifest_paths(manifest), strict=True):
            pdf = pdf_dir / local_name(entry.url)
            if ft3.is_file() and pdf.is_file():
                results.append(compare_entry(ft3, pdf, pdf.name))
            if len(results) >= limit:
                return results
    return results


def summary(results: list[FileResult]) -> str:
    compared = [result for result in results if result.oud_bars is not None and result.pdf_bars is not None]
    agree = sum(result.agrees for result in compared)
    differences = Counter((result.pdf_bars or 0) - (result.oud_bars or 0) for result in compared if not result.agrees)
    lines = [f"{len(results)} pairs, {len(compared)} measured, {agree} with equal bar counts"]
    lines.append(
        "difference (pdf - oud) histogram: "
        + ", ".join(f"{key:+d}:{count}" for key, count in sorted(differences.items())[:12])
    )
    return "\n".join(lines)


def _difference_line(result: FileResult) -> str:
    detail = f"oud {result.oud_bars}, pdf {result.pdf_bars}, lines {result.line_counts}"
    return f"  {result.name}: {detail} {result.error or ''}".rstrip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare decoded FT3 bar counts with reference PDF layouts.")
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--pdfs", type=Path, default=DEFAULT_PDFS)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--json", type=Path, help="write every result here")
    args = parser.parse_args(argv)
    results = collect(args.manifests, args.pdfs, limit=args.limit)
    print(summary(results))
    for result in results:
        if not result.agrees:
            print(_difference_line(result))
    if args.json:
        args.json.write_text(json.dumps([asdict(result) for result in results], indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
