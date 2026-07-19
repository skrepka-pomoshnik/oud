from __future__ import annotations

from oud.editor.init import init_state
from oud.editor.state import EditorState
from oud.editor.tab_reparse import apply_tab_reparse_delta
from oud.importers.tab import parse_tab_text_data
from petrucci.model import Bar, Piece


def _base_tab_text() -> str:
    return "\n".join(
        [
            "{Demo/Composer}",
            "b",
            "0a",
            "1b",
            "b",
            "0c",
            "1d",
            "e",
        ],
    )


def test_init_state_keeps_tab_data_for_tab_import(tmp_path) -> None:
    path = tmp_path / "demo.tab"
    path.write_text(_base_tab_text() + "\n", encoding="utf-8")
    config_path = tmp_path / "config.toml"
    state = init_state(str(path), config_path=str(config_path))
    assert state.tab_data is not None
    assert state.tab_data.source_lines == (_base_tab_text() + "\n").splitlines(keepends=True)
    assert len(state.piece.bars) == 2


def test_apply_tab_reparse_delta_updates_only_changed_bar_range() -> None:
    text = _base_tab_text()
    state = EditorState(Piece(title="T", bars=[Bar(), Bar()], strings=6), {"style": "french"})
    state.tab_data = _load_tab_data_from_text(text)
    state.piece = state.tab_data.piece
    changed = text.replace("1b", "1e")
    delta = apply_tab_reparse_delta(
        state,
        changed,
        changed_line_start=3,
        changed_line_end=3,
    )
    assert delta.full_reparse is False
    assert delta.old_bar_range == (0, 1)
    assert delta.new_bar_range == (0, 1)
    assert state.tab_data is not None
    assert [note.fret for note in state.piece.bars[0].chords[1].notes] == [4]
    assert [note.fret for note in state.piece.bars[1].chords[1].notes] == [3]


def test_apply_tab_reparse_delta_marks_header_change_as_full_reparse() -> None:
    text = _base_tab_text()
    state = EditorState(Piece(title="T", bars=[Bar(), Bar()], strings=6), {"style": "french"})
    state.tab_data = _load_tab_data_from_text(text)
    state.piece = state.tab_data.piece
    changed = text.replace("{Demo/Composer}", "{Changed/Composer}")
    delta = apply_tab_reparse_delta(
        state,
        changed,
        changed_line_start=0,
        changed_line_end=0,
    )
    assert delta.full_reparse is True
    assert delta.reason == "header_or_metadata_change"
    assert state.piece.title == "Changed"


def test_apply_tab_reparse_delta_auto_detects_body_edit() -> None:
    text = _base_tab_text()
    state = EditorState(Piece(title="T", bars=[Bar(), Bar()], strings=6), {"style": "french"})
    state.tab_data = _load_tab_data_from_text(text)
    state.piece = state.tab_data.piece
    changed = text.replace("0c", "0f")
    delta = apply_tab_reparse_delta(state, changed)
    assert delta.full_reparse is False
    assert delta.old_bar_range == (1, 2)
    assert delta.new_bar_range == (1, 2)
    assert [note.fret for note in state.piece.bars[1].chords[0].notes] == [5]


def _load_tab_data_from_text(text: str):
    parsed = parse_tab_text_data(text)
    assert parsed is not None
    return parsed
