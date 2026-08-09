import pytest

from oud.editor.core.state import EditorState
from oud.editor.services.validation.verify import bar_duration_sum, verify_bar, verify_render_bar
from petrucci.core.model import Bar, Chord, Note, Piece


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    settings = {
        "style": "french",
        "time": "C",
        "layout": "packed",
        "justify": "stretch",
        "barpad": "1",
        "fretlabelmode": "auto",
    }
    state = EditorState(piece, settings)
    state.screen_width = 80
    state.bar_width = 8
    return state


def test_bar_duration_sum_chords() -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(note_type=4, dotted=True, grid=None, notes=[Note(1, 0, 0)]),
        Chord(note_type=8, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
    ]
    total = bar_duration_sum(state, 0, default_duration=4)
    assert total == 1.5 + 0.0625


def test_bar_duration_sum_durations() -> None:
    state = _state()
    state.bar_width = 4
    state.durations[(0, 0, 0)] = 4
    state.durations[(0, 0, 2)] = 8
    total = bar_duration_sum(state, 0, default_duration=4)
    assert total == 2.5


def test_verify_bar_messages() -> None:
    state = _state()
    state.settings["time"] = "bad"
    assert verify_bar(state, 0) == "No valid time signature"
    state.settings["time"] = "4/4"
    state.piece.bars[0].chords = [Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]) for _ in range(4)]
    assert verify_bar(state, 0) == "Measure ok"
    state.piece.bars[0].chords = [Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]
    assert verify_bar(state, 0).startswith("Underfull")


def test_verify_bar_assignment_constraints_warning() -> None:
    state = _state()
    state.settings["time"] = "4/4"
    state.settings["tuning"] = "g2c3f3a3d4g4"
    state.settings["minimumfret"] = "1"
    state.settings["restrainopenstrings"] = "on"
    state.piece.bars[0].chords = [Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]) for _ in range(4)]
    msg = verify_bar(state, 0)
    assert msg.startswith("Assignment constraints:")


def test_verify_render_bar_ok_for_simple_chord() -> None:
    state = _state()
    state.piece.bars[0].chords = [Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]
    assert verify_render_bar(state, 0) == "Render ok"


def test_verify_render_bar_detects_non_monotonic_cursor_map(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _state()
    state.piece.bars[0].chords = [Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]
    monkeypatch.setattr("oud.editor.services.validation.verify.bar_content_width_for_cursor", lambda *_args: 8)
    monkeypatch.setattr(
        "oud.editor.services.validation.verify.cursor_display_map_for_bar", lambda *_args: [0, 2, 1, 3, 4, 5, 6, 7]
    )
    assert verify_render_bar(state, 0) == "Render map is non-monotonic"
