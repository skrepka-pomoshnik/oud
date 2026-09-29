from __future__ import annotations

from oud.editor.services.screen.pages import (
    info_lines,
    notes_lines,
    paint_ascii_preview,
    paint_page,
    paint_plugin_browser,
)
from oud.presentation.ui.adapter import CursesError, Screen
from petrucci.core.model import Bar, ImportedBarContent, ImportedScore, ImportedStaff, Piece


class _Screen(Screen):
    def __init__(self, h: int = 8, w: int = 40, *, raise_value: bool = False) -> None:
        self.h = h
        self.w = w
        self.raise_value = raise_value
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self.h, self.w

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        if self.raise_value:
            raise ValueError("bad")
        if y == self.h - 1 and x + len(text) >= self.w:
            raise CursesError("ERR")
        self.calls.append((y, x, text, attr))

    def erase(self) -> None:
        return None

    def refresh(self) -> None:
        return None


def test_info_and_notes_pages_describe_the_document() -> None:
    piece = Piece(
        title="T",
        bars=[Bar(melody_grid="3 3 8", lyrics=["Can", "Was she"])],
        strings=6,
        composer="C",
        arranger="A",
        subtitle="S",
        notes=["Ayres, v.1 (1597), f. c2v. Encoded and edited by Sarge Gerbode."],
        footnote="F",
        footnote_source="Src",
        footnote_editor="Ed",
        footnote_comment="Fc",
        comment="Commentary",
        key="Dm",
        piece_type="fantasia",
        difficulty="Challenge",
        ensemble="8-course, alto",
        part="score",
        source="Book I",
        editor="Editor",
        publisher="Publisher",
        volume="Vol. 1",
        page="12v",
        section_annotations={"section": "Performance"},
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(kind="note", label="alto", bars=[ImportedBarContent(source_bar_index=0)]),
                ImportedStaff(
                    kind="comment",
                    bars=[ImportedBarContent(source_bar_index=0, editorial_text=["Source comment"])],
                ),
            ],
        ),
        import_warnings=["Recovered partial TAB content."],
    )
    lines = info_lines(
        piece,
        {"style": "french", "time": "C", "filepath": "tests/fixtures/ft3/corpus/examples/x.ft3", "terminal": "120x38"},
    )
    assert lines[0] == "INFO"
    assert any(line.startswith("File:") for line in lines)
    assert any(line.startswith("Terminal:") for line in lines)
    assert any(line.startswith("Version:") for line in lines)
    assert any(line.startswith("Arranger:") and line.endswith("A") for line in lines)
    assert any(line.startswith("FootSrc:") and line.endswith("Src") for line in lines)
    assert any(line.startswith("FootEd:") and line.endswith("Ed") for line in lines)
    assert any(line.startswith("FootCmt:") and line.endswith("Fc") for line in lines)
    assert any(line.startswith("Comment:") and line.endswith("Commentary") for line in lines)
    assert any(line.startswith("Source page:") and line.endswith("12v") for line in lines)
    assert "Imported score: ft3" in lines
    assert "Staff 1: note | alto | 1 bars" in lines
    assert "section: Performance" in lines
    assert any(line.startswith("LyricBars:") and line.endswith("1") for line in lines)
    assert any(line.startswith("MelodyBars:") and line.endswith("1") for line in lines)
    assert "Import warnings" in lines
    assert any("Recovered partial TAB content" in line for line in lines)
    notes = notes_lines(piece)
    assert notes[0] == "NOTES"
    assert any("Sarge Gerbode" in line for line in notes)
    assert "[1] Source comment" in notes
    s = _Screen(h=6, w=30)
    paint_page(s, ["HELP", "line"], offset=0, status="help", status_attr=1)
    paint_plugin_browser(s, title="Plugins", items=["a", "b"], index=1, offset=0, message="msg", status_attr=1)
    assert (2, 0, "> b", 1) in s.calls
    assert s.calls


def test_paint_page_clamps_offset_to_the_last_full_page() -> None:
    s = _Screen(h=4, w=30)
    paint_page(s, [f"line {index}" for index in range(10)], offset=99, status="info", status_attr=1)
    assert [call[2] for call in s.calls] == ["line 7", "line 8", "line 9", "info"]


def test_ascii_preview_leaves_the_last_row_to_a_visible_status() -> None:
    lines = [f"row {index}" for index in range(10)]
    with_status = _Screen(h=4, w=30)
    paint_ascii_preview(with_status, lines, status="status", status_attr=1)
    assert [call[2] for call in with_status.calls] == ["row 0", "row 1", "row 2", "status"]
    hidden = _Screen(h=4, w=30)
    paint_ascii_preview(hidden, lines, status=None, status_attr=1)
    assert [call[2] for call in hidden.calls] == ["row 0", "row 1", "row 2", "row 3"]
