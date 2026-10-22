from __future__ import annotations

from pathlib import Path

import pytest

from petrucci.core.model import Bar, Chord, Note, Piece
from scripts.corpus import render_compare
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


def test_comparison_engraves_the_source_tuning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    piece = Piece(
        title="Source tuning",
        strings=6,
        tuning="a2d3g3b3e4a4",
        bars=[Bar(chords=[Chord(4, False, None, [Note(1, 0, 0)])])],
    )
    monkeypatch.setattr(render_compare, "load_ft3", lambda _path: piece)
    monkeypatch.setattr(render_compare.subprocess, "run", lambda *_args, **_kwargs: None)

    render_compare.compile_ly(tmp_path / "source.ft3", tmp_path)

    source = (tmp_path / "piece.ly").read_text(encoding="utf-8")
    assert "stringTunings = \\stringTuning <a, d g b e' a'>" in source
    assert "a'4\\1" in source
