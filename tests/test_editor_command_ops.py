from core.model import Bar, Piece
from editor.command_ops import (
    cmd_bar,
    cmd_chord,
    cmd_stave,
    paste_bar,
    row_first_note_col,
    show_help,
    yank_bar,
)
from editor.state import EditorState


def _state(bars: int = 2) -> EditorState:
    piece = Piece(title="T", bars=[Bar() for _ in range(bars)], strings=6)
    settings = {
        "style": "french",
        "keys": "vim+arrows",
        "spacingmode": "packed",
        "linelen": "80",
        "bargap": "1",
    }
    state = EditorState(piece, settings)
    state.screen_width = 80
    return state


def test_row_first_note_col() -> None:
    state = _state()
    state.overrides[(0, 0, 3)] = "a"
    state.overrides[(0, 0, 1)] = "b"
    assert row_first_note_col(state) == 1


def test_yank_and_paste_bar() -> None:
    state = _state()
    state.overrides[(0, 0, 0)] = "a"
    state.durations[(0, 0, 0)] = 4
    state.annotations[(0, 0)] = "ann"
    state.ornaments[(0, 0)] = "orn"
    state.dotted.add((0, 0))
    state.slurs.append((0, 0, 1))
    state.ties.append((0, 0, 1))
    state.holds.append((0, 0, 1))
    yank_bar(state, 0)
    assert state.yanked_bar is not None
    paste_bar(state, 1)
    assert len(state.piece.bars) == 3
    assert state.overrides[(1, 0, 0)] == "a"


def test_cmd_bar_and_stave() -> None:
    state = _state()
    cmd_bar(state, "add")
    assert state.message == "Bar added"
    cmd_bar(state, "del")
    assert state.message == "Bar deleted"
    state.cursor_bar = 0
    cmd_stave(state, "break")
    assert state.message == "Stave break added"
    cmd_stave(state, "join")
    assert state.message == "Stave break removed"
    cmd_stave(state, "new")
    assert state.message == "Stave inserted"
    cmd_stave(state, "del")
    assert state.message == "Stave deleted"
    cmd_stave(state, "other")
    assert state.message == "Stave action: break/join/new/del"


def test_cmd_chord() -> None:
    state = _state()
    cmd_chord(state, "insert")
    assert state.piece.bars[state.cursor_bar].chords
    cmd_chord(state, "delete")
    assert state.piece.bars[state.cursor_bar].chords == []
    cmd_chord(state, "other")
    assert state.message == "Chord action: add/del"


def test_show_help_uses_less(monkeypatch) -> None:
    state = _state()
    calls: list[list[str]] = []

    monkeypatch.setattr("editor.command_ops.shutil.which", lambda _name: "less")

    def fake_run(args, check=False):  # noqa: ARG001
        calls.append(list(args))

    monkeypatch.setattr("editor.command_ops.subprocess.run", fake_run)
    show_help(state)
    assert calls
    assert calls[0][0] == "less"
