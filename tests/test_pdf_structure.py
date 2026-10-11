"""Measuring the staves and bars of a rasterised page, on bitmaps built in the test."""

from __future__ import annotations

import pytest

from scripts.corpus.pdf_structure import PdfStructureError, analyse_bitmap, read_pgm

WIDTH, HEIGHT = 200, 120


def _page(systems: list[tuple[int, list[int]]], *, spacing: int = 6) -> tuple[int, int, bytes]:
    """White page; each system is (top row, barline columns) with six staff lines drawn across it."""

    pixels = bytearray([255] * (WIDTH * HEIGHT))
    for top, barlines in systems:
        for line in range(6):
            row = top + line * spacing
            for column in range(10, WIDTH - 10):
                pixels[row * WIDTH + column] = 0
        for column in barlines:
            for row in range(top, top + 5 * spacing + 1):
                pixels[row * WIDTH + column] = 0
    return WIDTH, HEIGHT, bytes(pixels)


def test_read_pgm_returns_the_pixels() -> None:
    data = b"P5\n# comment\n2 2\n255\n" + bytes([0, 255, 255, 0])

    assert read_pgm(data) == (2, 2, bytes([0, 255, 255, 0]))


def test_something_that_is_not_a_bitmap_is_refused() -> None:
    with pytest.raises(PdfStructureError):
        read_pgm(b"P6 1 1 255 abc")


def test_a_system_with_four_bars_has_five_barlines() -> None:
    page = analyse_bitmap(*_page([(10, [10, 60, 110, 160, 189])]))

    assert [(system.lines, system.bars) for system in page.systems] == [(6, 4)]


def test_two_systems_are_separate() -> None:
    page = analyse_bitmap(*_page([(10, [10, 100, 189]), (70, [10, 70, 130, 189])]))

    assert [system.bars for system in page.systems] == [2, 3]


def test_a_double_barline_counts_once() -> None:
    page = analyse_bitmap(*_page([(10, [10, 100, 103, 189])]))

    assert page.systems[0].bars == 2


def test_a_row_of_scattered_beams_is_not_a_staff_line() -> None:
    width, height, pixels = _page([(40, [10, 189])])
    grid = bytearray(pixels)
    for start in range(20, 190, 20):  # short beams every 20 columns on one row above the staff
        for column in range(start, start + 6):
            grid[20 * width + column] = 0

    page = analyse_bitmap(width, height, bytes(grid))

    assert [system.lines for system in page.systems] == [6]
