from fractions import Fraction

from oud.editor.core.state import EditorState
from petrucci.core.model import Bar, Piece


def test_clamp_bounds_cursor() -> None:
    piece = Piece(title="T", bars=[Bar(), Bar()])
    state = EditorState(piece, {"style": "french"})
    state.cursor_bar = 5
    state.cursor_string = 9
    state.cursor_onset = Fraction(7)
    state.bar_width = 4
    state.clamp()
    assert state.cursor_bar == 1
    assert state.cursor_string == piece.strings - 1
    assert state.cursor_onset == 0


def test_clamp_minimums() -> None:
    piece = Piece(title="T", bars=[Bar()])
    state = EditorState(piece, {"style": "french"})
    state.cursor_bar = -3
    state.cursor_string = -2
    state.cursor_col = -1
    state.clamp()
    assert state.cursor_bar == 0
    assert state.cursor_string == 0
    assert state.cursor_col == 0


def test_state_slices_keep_legacy_aliases() -> None:
    piece = Piece(title="T", bars=[Bar()])
    state = EditorState(piece, {"style": "french"})

    state.command_history = ["w", "q"]
    assert state.history.command == ["w", "q"]
    state.search_history = ["foo"]
    assert state.history.search == ["foo"]

    state.playback_timeline = []
    state.playback_started_at = 12.3
    state.playback_index = 4
    state.playback_bar = 2
    state.playback_col = 5
    assert state.playback.started_at == 12.3
    assert state.playback.index == 4
    assert state.playback.bar == 2
    assert state.playback.col == 5

    state.plugin_title = "Lutemusic"
    state.plugin_query = "frog"
    state.plugin_query_active = True
    state.plugin_pending = "g"
    assert state.plugins.title == "Lutemusic"
    assert state.plugins.query == "frog"
    assert state.plugins.query_active is True
    assert state.plugins.pending == "g"
