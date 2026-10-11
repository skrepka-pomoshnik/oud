"""Measuring the staves and bars of a rasterised page, on bitmaps built in the test."""

from __future__ import annotations

from itertools import pairwise

import pytest

from scripts.corpus.pdf_structure import PdfStructureError, analyse_bitmap, read_pgm

WIDTH, HEIGHT = 200, 160


def _draw_staff(pixels: bytearray, top: int, spacing: int) -> None:
    for line in range(6):
        row = top + line * spacing
        for column in range(10, WIDTH - 10):
            pixels[row * WIDTH + column] = 0


def _draw_bars(pixels: bytearray, top: int, spacing: int, barlines: list[int]) -> None:
    for column in barlines:
        for row in range(top, top + 5 * spacing + 1):
            pixels[row * WIDTH + column] = 0
    for left, right in pairwise(barlines):  # a rhythm flag above each bar
        for row in range(top - 20, top - 6):
            pixels[row * WIDTH + (left + right) // 2] = 0


def _page(systems: list[tuple[int, list[int]]], *, spacing: int = 6) -> tuple[int, int, bytes]:
    """White page; each system is (top row, barline columns): six staff lines, barlines and a flag over each bar."""

    pixels = bytearray([255] * (WIDTH * HEIGHT))
    for top, barlines in systems:
        _draw_staff(pixels, top, spacing)
        _draw_bars(pixels, top, spacing, barlines)
    return WIDTH, HEIGHT, bytes(pixels)


def test_read_pgm_returns_the_pixels() -> None:
    data = b"P5\n# comment\n2 2\n255\n" + bytes([0, 255, 255, 0])

    assert read_pgm(data) == (2, 2, bytes([0, 255, 255, 0]))


def test_something_that_is_not_a_bitmap_is_refused() -> None:
    with pytest.raises(PdfStructureError):
        read_pgm(b"P6 1 1 255 abc")


def test_a_system_with_four_bars_has_five_barlines() -> None:
    page = analyse_bitmap(*_page([(30, [10, 60, 110, 160, 189])]))

    assert [(system.lines, system.bars) for system in page.systems] == [(6, 4)]


def test_two_systems_are_separate() -> None:
    page = analyse_bitmap(*_page([(30, [10, 100, 189]), (90, [10, 70, 130, 189])]))

    assert [system.bars for system in page.systems] == [2, 3]


def test_a_double_barline_counts_once() -> None:
    page = analyse_bitmap(*_page([(30, [10, 100, 103, 189])]))

    assert page.systems[0].bars == 2


def test_a_span_without_rhythm_flags_is_not_a_bar() -> None:
    """The meter sign between a double barline and a repeat sign holds no flags."""

    width, height, pixels = _page([(40, [10, 100, 189])])
    grid = bytearray(pixels)
    for row in range(40 - 20, 40 - 6):  # clear the flag over the second bar
        grid[row * width + 144] = 255

    system = analyse_bitmap(width, height, bytes(grid)).systems[0]

    assert (system.bars, system.bars_with_flags) == (2, 1)  # two spans, only one holds a flag


def test_a_row_of_scattered_beams_is_not_a_staff_line() -> None:
    width, height, pixels = _page([(40, [10, 189])])
    grid = bytearray(pixels)
    for start in range(20, 190, 20):  # short beams every 20 columns on one row above the staff
        for column in range(start, start + 6):
            grid[20 * width + column] = 0

    page = analyse_bitmap(width, height, bytes(grid))

    assert [system.lines for system in page.systems] == [6]
