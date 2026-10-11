from __future__ import annotations

from scripts.corpus.pdf_structure import PageShape, SystemShape
from scripts.corpus.render_compare import Layout, RenderResult, measure, summary


def _system(lines: int, barlines: int) -> SystemShape:
    return SystemShape(top=0, bottom=40, lines=lines, barlines=tuple(range(barlines)))


def test_measure_counts_pages_tablature_systems_and_bars() -> None:
    pages = [PageShape(612, 792, (_system(6, 4), _system(5, 9))), PageShape(612, 792, (_system(6, 3),))]

    assert measure(pages) == Layout(pages=2, systems=2, bars=5)


def test_summary_counts_agreement_and_ignores_failed_files() -> None:
    results = [
        RenderResult("a", Layout(1, 8, 30), Layout(1, 9, 31)),
        RenderResult("b", Layout(2, 8, 30), Layout(1, 12, 31)),
        RenderResult("c", None, None, "TimeoutExpired"),
    ]

    assert summary(results) == "3 files, 2 compiled, 1 with the same page count, 1 with the system count within 1"
