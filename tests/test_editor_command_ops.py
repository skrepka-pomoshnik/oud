from oud.editor.command_ops import (
    cmd_bar,
    cmd_chord,
    cmd_stave,
    paste_bar,
    row_first_note_col,
    show_help,
    yank_bar,
)
from oud.editor.state import EditorState
from oud.editor.undo_ops import redo, undo
from oud.petrucci.model import Bar, Piece


def _state(bars: int = 2) -> EditorState:
    piece = Piece(title="T", bars=[Bar() for _ in range(bars)], strings=6)
    settings = {
        "style": "french",
        "keys": "vim+arrows",
        "layout": "packed",
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
    state.glisses.append((0, 0, 1))
    state.marks["a"] = (0, 0, 0)
    yank_bar(state, 0)
    assert state.yanked_bar is not None
    paste_bar(state, 1)
    assert len(state.piece.bars) == 3
    assert state.overrides[(1, 0, 0)] == "a"
    assert (1, 0, 1) in state.glisses
    assert state.marks["a"] == (1, 0, 0)
    assert state.message == "Bar pasted"
    assert state.undo_stack[-1].kind == "bars-insert"
    undo(state, config_path=state.config_path)
    assert len(state.piece.bars) == 2
    assert (1, 0, 0) not in state.overrides
    assert (1, 0, 1) not in state.glisses
    redo(state, config_path=state.config_path)
    assert len(state.piece.bars) == 3
    assert state.overrides[(1, 0, 0)] == "a"
    assert (1, 0, 1) in state.glisses
    assert state.marks["a"] == (1, 0, 0)


def test_yank_and_paste_multiple_bars() -> None:
    state = _state(bars=3)
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(1, 0, 1)] = "b"
    yank_bar(state, 0, count=2)
    assert state.yanked_bars is not None
    assert len(state.yanked_bars) == 2
    paste_bar(state, 2)
    assert len(state.piece.bars) == 5
    assert state.overrides[(2, 0, 0)] == "a"
    assert state.overrides[(3, 0, 1)] == "b"
    assert state.message == "Bars pasted: 2"
    assert state.undo_stack[-1].kind == "bars-insert"
    undo(state, config_path=state.config_path)
    assert len(state.piece.bars) == 3
    assert (2, 0, 0) not in state.overrides
    assert (3, 0, 1) not in state.overrides


def test_cmd_bar_and_stave() -> None:
    state = _state()
    cmd_bar(state, "add")
    assert state.message == "Bar added"
    cmd_bar(state, "del")
    assert state.message == "Bar deleted"
    state = _state(bars=4)
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(1, 0, 1)] = "b"
    cmd_bar(state, "yank 2")
    assert state.message == "Bars yanked: 2"
    cmd_bar(state, "paste 2")
    assert state.message == "Bars pasted: 4"
    assert len(state.piece.bars) == 8
    cmd_bar(state, "del 3")
    assert state.message == "Bars deleted: 3"
    assert len(state.piece.bars) == 5
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
    cmd_bar(state, "other")
    assert state.message == "Bar action: add/after/before/insert/del/yank/paste [count]"


def test_multi_bar_delete_does_not_double_shift_stave_breaks() -> None:
    state = _state(bars=8)
    state.stave_breaks = {6}
    state.cursor_bar = 2
    cmd_bar(state, "del 2")
    assert state.stave_breaks == {4}


def test_bar_insert_delete_reindexes_glisses_and_marks() -> None:
    state = _state(bars=3)
    state.glisses = [(2, 0, 1)]
    state.marks["a"] = (2, 0, 1)
    cmd_bar(state, "add")
    assert state.glisses == [(3, 0, 1)]
    assert state.marks["a"] == (3, 0, 1)
    state.cursor_bar = 1
    cmd_bar(state, "del")
    assert state.glisses == [(2, 0, 1)]
    assert state.marks["a"] == (2, 0, 1)
    state.cursor_bar = 2
    cmd_bar(state, "del")
    assert state.glisses == []
    assert "a" not in state.marks


def test_cmd_chord() -> None:
    state = _state()
    cmd_chord(state, "insert 3")
    assert len(state.piece.bars[state.cursor_bar].chords) == 3
    assert state.message == "Chords added: 3"
    state.cursor_col = 0
    cmd_chord(state, "yank 2")
    assert state.yanked_chords is not None
    assert len(state.yanked_chords) == 2
    assert state.message == "Chords yanked: 2"
    state.cursor_col = state.bar_width - 1
    cmd_chord(state, "paste")
    assert len(state.piece.bars[state.cursor_bar].chords) == 5
    assert state.message == "Chords pasted: 2"
    state.cursor_col = 0
    cmd_chord(state, "delete 2")
    assert len(state.piece.bars[state.cursor_bar].chords) == 3
    assert state.message == "Chords deleted: 2"
    cmd_chord(state, "delete")
    assert len(state.piece.bars[state.cursor_bar].chords) == 2
    state.cursor_col = 0
    cmd_chord(state, "delete 2")
    assert state.piece.bars[state.cursor_bar].chords == []
    state.yanked_chords = None
    cmd_chord(state, "paste")
    assert state.message == "No yanked chords"
    cmd_chord(state, "other")
    assert state.message == "Chord action: add/del/yank/paste [count]"


def test_show_help_uses_less(monkeypatch) -> None:
    state = _state()
    calls: list[list[str]] = []

    monkeypatch.setattr("oud.editor.command_ops.shutil.which", lambda _name: "less")

    def fake_run(args, check=False):  # noqa: ARG001
        calls.append(list(args))

    monkeypatch.setattr("oud.editor.command_ops.subprocess.run", fake_run)
    show_help(state)
    assert calls
    assert calls[0][0] == "less"
