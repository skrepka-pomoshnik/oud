#!/usr/bin/env python3
"""Measure the structure of a reference PDF page: its systems and the bars on each.

A page is rasterised with ``pdftoppm`` (poppler) to a grey bitmap. Staff lines are the rows that are dark across
most of the page; staves are runs of such lines at an even spacing; barlines are columns that are dark through
the whole height of a staff. This reads the *layout* of the typeset page, so Oud's engraving can be compared with
it without pixel identity.
"""

from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

DPI = 100
DARK = 128
LINE_COVERAGE = 0.30  # a staff line is dark across at least this share of the page width
LINE_DENSITY = 0.75  # and dark over this share of the extent it covers
BARLINE_COVERAGE = 0.85  # a barline is dark through at least this share of the staff height
SYSTEM_GAP_FACTOR = 2.2  # lines further apart than this many line spacings start a new staff
MIN_STAFF_LINES = 4
PGM_MAGIC = b"P5"
PGM_HEADER_FIELDS = 3  # width, height, maximum grey value
MIN_STAFF_CENTRES = 2
ERR_NOT_PGM = "expected a binary PGM bitmap"
ERR_RASTER = "cannot rasterise {}: {}"
POPPLER_TIMEOUT = 60


@dataclass(frozen=True)
class SystemShape:
    top: int
    bottom: int
    lines: int
    barlines: tuple[int, ...]

    @property
    def bars(self) -> int:
        return max(0, len(self.barlines) - 1)


@dataclass(frozen=True)
class PageShape:
    width: int
    height: int
    systems: tuple[SystemShape, ...]


class PdfStructureError(RuntimeError):
    pass


def read_pgm(data: bytes) -> tuple[int, int, bytes]:
    """Width, height and pixels of a binary (P5) grey bitmap."""

    if not data.startswith(PGM_MAGIC):
        raise PdfStructureError(ERR_NOT_PGM)
    tokens: list[bytes] = []
    position = 2
    while len(tokens) < PGM_HEADER_FIELDS:
        while data[position : position + 1].isspace():
            position += 1
        if data[position : position + 1] == b"#":
            position = data.index(b"\n", position) + 1
            continue
        end = position
        while not data[end : end + 1].isspace():
            end += 1
        tokens.append(data[position:end])
        position = end
    width, height = int(tokens[0]), int(tokens[1])
    return width, height, data[position + 1 : position + 1 + width * height]


def _is_staff_line(row: bytes, width: int) -> bool:
    """Dark across a wide extent with few gaps: letters may cut a line, a row of scattered beams may not pass."""

    dark = [column for column, value in enumerate(row) if value < DARK]
    if len(dark) < width * LINE_COVERAGE:
        return False
    extent = dark[-1] - dark[0] + 1
    return extent >= width * LINE_COVERAGE and len(dark) >= extent * LINE_DENSITY


def _line_rows(width: int, height: int, pixels: bytes) -> list[int]:
    return [row for row in range(height) if _is_staff_line(pixels[row * width : (row + 1) * width], width)]


def _merge_runs(values: list[int]) -> list[float]:
    """Centres of runs of consecutive integers (a thick staff line is a run of rows)."""

    centres: list[float] = []
    run: list[int] = []
    for value in values:
        if run and value != run[-1] + 1:
            centres.append(sum(run) / len(run))
            run = []
        run.append(value)
    if run:
        centres.append(sum(run) / len(run))
    return centres


def _staves(centres: list[float]) -> list[list[float]]:
    if len(centres) < MIN_STAFF_CENTRES:
        return []
    spacing = statistics.median(later - earlier for earlier, later in pairwise(centres))
    staves: list[list[float]] = [[centres[0]]]
    for centre in centres[1:]:
        if centre - staves[-1][-1] > spacing * SYSTEM_GAP_FACTOR:
            staves.append([])
        staves[-1].append(centre)
    return [staff for staff in staves if len(staff) >= MIN_STAFF_LINES]


def _barlines(width: int, pixels: bytes, top: int, bottom: int) -> tuple[int, ...]:
    height = bottom - top + 1
    needed = height * BARLINE_COVERAGE
    columns = [
        column
        for column in range(width)
        if sum(1 for row in range(top, bottom + 1) if pixels[row * width + column] < DARK) >= needed
    ]
    return tuple(int(centre) for centre in _merge_runs(_close_gaps(columns)))


def _close_gaps(columns: list[int], gap: int = 4) -> list[int]:
    """Fill gaps of a few pixels so a double barline (thin and thick) counts once."""

    filled: list[int] = []
    for column in columns:
        if filled and column - filled[-1] <= gap:
            filled.extend(range(filled[-1] + 1, column))
        filled.append(column)
    return filled


def analyse_bitmap(width: int, height: int, pixels: bytes) -> PageShape:
    centres = _merge_runs(_line_rows(width, height, pixels))
    systems = []
    for staff in _staves(centres):
        top, bottom = int(staff[0]), int(staff[-1])
        systems.append(SystemShape(top, bottom, len(staff), _barlines(width, pixels, top, bottom)))
    return PageShape(width, height, tuple(systems))


def analyse_pdf(path: Path, *, dpi: int = DPI) -> list[PageShape]:
    """The shape of every page of ``path``."""

    with tempfile.TemporaryDirectory() as folder:
        prefix = Path(folder) / "page"
        try:
            subprocess.run(  # noqa: S603 - fixed argument list, no shell
                ["pdftoppm", "-gray", "-r", str(dpi), str(path), str(prefix)],  # noqa: S607
                check=True,
                capture_output=True,
                timeout=POPPLER_TIMEOUT,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PdfStructureError(ERR_RASTER.format(path.name, exc)) from exc
        return [analyse_bitmap(*read_pgm(page.read_bytes())) for page in sorted(Path(folder).glob("page-*.pgm"))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the systems and bars of reference PDF pages.")
    parser.add_argument("pdfs", nargs="+", type=Path)
    args = parser.parse_args(argv)
    for path in args.pdfs:
        pages = analyse_pdf(path)
        bars = sum(system.bars for page in pages for system in page.systems)
        print(f"{path.name}: {len(pages)} pages, {bars} bars")
        for number, page in enumerate(pages, start=1):
            print(f"  page {number}: " + ", ".join(f"{s.bars}b/{s.lines}l" for s in page.systems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
