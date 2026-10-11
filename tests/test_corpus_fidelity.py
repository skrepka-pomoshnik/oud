"""The corpus comparison's summary and tablature-staff counting, on made-up page shapes."""

from __future__ import annotations

from scripts.corpus.fidelity import FileResult, _pdf_summary, summary
from scripts.corpus.pdf_structure import PageShape, SystemShape


def _system(lines: int, bars: int) -> SystemShape:
    return SystemShape(top=0, bottom=10, lines=lines, barlines=tuple(range(bars + 1)))


def test_only_staves_with_six_or_more_lines_count_as_tablature() -> None:
    page = PageShape(100, 100, (_system(5, 4), _system(6, 3), _system(8, 2)))

    assert _pdf_summary([page]) == (5, 0, 2, (5, 6, 8))


def test_the_summary_counts_agreements_and_lists_the_differences() -> None:
    results = [
        FileResult("a.pdf", 10, 10, 10, 1, 2, (6,)),
        FileResult("b.pdf", 10, 13, 12, 1, 2, (6,)),
        FileResult("c.pdf", None, None, None, 0, 0, (), "ft3: broken"),
    ]

    text = summary(results)

    assert text.splitlines()[0] == "3 pairs, 2 measured, 1 with a bar count inside the measured bounds"
    assert "+2:1" in text


def test_a_count_inside_the_bounds_agrees() -> None:
    assert FileResult("a.pdf", 11, 12, 10, 1, 1, (6,)).agrees
    assert not FileResult("a.pdf", 9, 12, 10, 1, 1, (6,)).agrees
    assert not FileResult("a.pdf", 13, 12, 10, 1, 1, (6,)).agrees
