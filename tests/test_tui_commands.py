from core.model import Bar, Chord, Note, Piece
from editor.command_ops import convert_overrides
from editor.edit_ops import apply_duration
from editor.state import EditorState
from editor.verify_ops import bar_duration_sum
from tui.commands import _parse_time_sig_value, _tuning_preset


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    return EditorState(piece, {"style": "french"})


def test_parse_time_sig_value() -> None:
    assert _parse_time_sig_value("C") == (4, 4)
    assert _parse_time_sig_value("O") == (3, 4)
    assert _parse_time_sig_value("6/8") == (6, 8)
    assert _parse_time_sig_value("bad") is None


def test_tuning_preset() -> None:
    assert _tuning_preset("renaissance") == "g2c3f3a3d4g4"
    assert _tuning_preset("unknown") is None


def test_bar_duration_sum_with_chords() -> None:
    state = _state()
    chord = Chord(note_type=4, dotted=True, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [chord]
    total = bar_duration_sum(state, 0, default_duration=4)
    assert total == 1.5


def test_bar_duration_sum_with_durations() -> None:
    state = _state()
    state.bar_width = 4
    state.durations[(0, 0, 0)] = 4
    state.durations[(0, 0, 1)] = 4
    state.durations[(0, 0, 2)] = 8
    total = bar_duration_sum(state, 0, default_duration=4)
    assert total == 2.5


def test_apply_duration_replaces_column() -> None:
    state = _state()
    state.durations[(0, 1, 0)] = 4
    apply_duration(state, (0, 0, 0), 8)
    assert state.durations[(0, 0, 0)] == 8
    assert (0, 1, 0) not in state.durations


def test_convert_overrides_updates_message() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(0, 0, 1)] = "z"
    convert_overrides(state, "italian")
    assert state.overrides[(0, 0, 0)] == "0"
    assert state.overrides[(0, 0, 1)] == "z"
    assert "Converted" in state.message
