#!/usr/bin/env python3
"""Typeset corpus FT3 files with the gerbode LilyPond profile and compare the page layout with the reference PDFs.

Local and untracked inputs, like ``fidelity.py``. Every file is exported to LilyPond source, compiled with a
finite timeout, and both PDFs are measured with ``pdf_structure``: pages, tablature systems and bars. The result
shows how close Oud's pagination is to Gerbode's, not whether the notes are right (``fidelity.py`` checks that).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from oud.exports.lilypond import export_lilypond
from oud.importers.ft3 import load_ft3
from oud.settings import DEFAULT_SETTINGS
from scripts.corpus.fetch import load_manifest, manifest_paths
from scripts.corpus.pdf_structure import PageShape, PdfStructureError, analyse_pdf
from scripts.corpus.pdfs import local_name

DEFAULT_PDFS = Path("downloads/gerbode/pdf")
LILYPOND = "lilypond-2.26"
COMPILE_TIMEOUT = 180
TAB_LINES = 6
SYSTEM_TOLERANCE = 1
GERBODE_SETTINGS = {"lyprofile": "gerbode", "lytabrhythm": "full", "lypapersize": "letter"}


@dataclass(frozen=True)
class Layout:
    pages: int
    systems: int
    bars: int


@dataclass(frozen=True)
class RenderResult:
    name: str
    oud: Layout | None
    reference: Layout | None
    error: str | None = None

    @property
    def same_pages(self) -> bool:
        return self.oud is not None and self.reference is not None and self.oud.pages == self.reference.pages

    @property
    def near_systems(self) -> bool:
        if self.oud is None or self.reference is None:
            return False
        return abs(self.oud.systems - self.reference.systems) <= SYSTEM_TOLERANCE


def measure(pages: list[PageShape]) -> Layout:
    """Pages, tablature systems (six or more lines) and the bars between their barlines."""

    systems = [system for page in pages for system in page.systems if system.lines >= TAB_LINES]
    return Layout(len(pages), len(systems), sum(system.bars for system in systems))


def compile_ly(ft3: Path, workdir: Path) -> Path:
    piece = load_ft3(str(ft3))
    source = workdir / "piece.ly"
    settings = {**DEFAULT_SETTINGS, **GERBODE_SETTINGS}
    if piece.tuning:
        settings["tuning"] = piece.tuning
    if piece.style:
        settings["style"] = piece.style
    export_lilypond(str(source), piece, {}, {}, 12, settings=settings)
    subprocess.run(  # noqa: S603 - fixed argument list, no shell
        [LILYPOND, "-dno-point-and-click", "-o", str(workdir / "piece"), str(source)],
        check=True,
        capture_output=True,
        timeout=COMPILE_TIMEOUT,
    )
    return workdir / "piece.pdf"


def compare_entry(ft3: Path, reference: Path, name: str) -> RenderResult:
    try:
        ref_layout = measure(analyse_pdf(reference))
        with tempfile.TemporaryDirectory(prefix="oud-render-") as tmp:
            oud_layout = measure(analyse_pdf(compile_ly(ft3, Path(tmp))))
    except (OSError, ValueError, subprocess.SubprocessError, PdfStructureError) as exc:
        return RenderResult(name, None, None, f"{type(exc).__name__}: {exc}"[:200])
    return RenderResult(name, oud_layout, ref_layout)


def collect(manifests: list[Path], pdf_dir: Path, *, limit: int, jobs: int) -> list[RenderResult]:
    pairs: list[tuple[Path, Path, str]] = []
    for manifest_path in manifests:
        manifest = load_manifest(manifest_path)
        for entry, ft3 in zip(manifest.files, manifest_paths(manifest), strict=True):
            pdf = pdf_dir / local_name(entry.url)
            if ft3.is_file() and pdf.is_file():
                pairs.append((ft3, pdf, pdf.name))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(lambda pair: compare_entry(*pair), pairs[:limit]))


def summary(results: list[RenderResult]) -> str:
    measured = [result for result in results if result.oud is not None]
    pages = sum(result.same_pages for result in measured)
    systems = sum(result.near_systems for result in measured)
    return (
        f"{len(results)} files, {len(measured)} compiled, {pages} with the same page count, "
        f"{systems} with the system count within {SYSTEM_TOLERANCE}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare gerbode-profile LilyPond pages with reference PDFs.")
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--pdfs", type=Path, default=DEFAULT_PDFS)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--json", type=Path, help="write every result here")
    args = parser.parse_args(argv)
    results = collect(args.manifests, args.pdfs, limit=args.limit, jobs=args.jobs)
    print(summary(results))
    for result in results:
        if result.error or not (result.same_pages and result.near_systems):
            print(f"  {result.name}: oud {result.oud}, reference {result.reference} {result.error or ''}".rstrip())
    if args.json:
        args.json.write_text(json.dumps([asdict(result) for result in results], indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
