from __future__ import annotations

from pathlib import Path

from oud.core.model import Bar, Chord, Note, Piece
from oud.editor.bar_ops import snapshot_bar
from oud.editor.state import EditorState, UndoAction
from oud.editor.undo_ops import apply_action, redo, undo


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar(), Bar()], strings=6)
    settings = {"style": "french", "time": "C"}
    return EditorState(piece, settings)


def test_apply_action_simple_flags(tmp_path: Path) -> None:
    state = _state()
    config_path = str(tmp_path / "cfg.toml")
    apply_action(
        state,
        UndoAction(kind="override", data={"key": (0, 0, 0), "prev": None, "new": "a"}),
        redo=True,
        config_path=config_path,
    )
    assert state.overrides[(0, 0, 0)] == "a"
    apply_action(
        state,
        UndoAction(kind="duration", data={"key": (0, 0, 0), "prev": None, "new": 8}),
        redo=True,
        config_path=config_path,
    )
    assert state.durations[(0, 0, 0)] == 8
    apply_action(
        state,
        UndoAction(
            kind="duration_col",
            data={"bar": 0, "col": 0, "prev": {}, "new": {(0, 0, 0): 4}},
        ),
        redo=True,
        config_path=config_path,
    )
    assert state.durations[(0, 0, 0)] == 4
    apply_action(
        state,
        UndoAction(kind="dotted", data={"key": (0, 0), "prev": False, "new": True}),
        redo=True,
        config_path=config_path,
    )
    assert (0, 0) in state.dotted
    apply_action(
        state,
        UndoAction(kind="ornament", data={"key": (0, 0), "prev": None, "new": "tr"}),
        redo=True,
        config_path=config_path,
    )
    assert state.ornaments[(0, 0)] == "tr"
    apply_action(
        state,
        UndoAction(kind="annotation", data={"key": (0, 0), "prev": None, "new": "x"}),
        redo=True,
        config_path=config_path,
    )
    assert state.annotations[(0, 0)] == "x"
    apply_action(
        state,
        UndoAction(kind="highlight", data={"key": (0, 0, 0), "prev": False, "new": True}),
        redo=True,
        config_path=config_path,
    )
    assert (0, 0, 0) in state.highlights


def test_apply_action_structural(tmp_path: Path) -> None:
    state = _state()
    config_path = str(tmp_path / "cfg.toml")
    apply_action(
        state,
        UndoAction(kind="barline", data={"bar": 0, "prev": None, "new": "thin"}),
        redo=True,
        config_path=config_path,
    )
    assert state.piece.bars[0].barline == "thin"
    apply_action(
        state,
        UndoAction(kind="repeat", data={"bar": 0, "prev": None, "new": "start"}),
        redo=True,
        config_path=config_path,
    )
    assert state.piece.bars[0].repeat == "start"
    apply_action(
        state,
        UndoAction(
            kind="timesig",
            data={
                "bar": 0,
                "prev": None,
                "new": "3/4",
                "setting_prev": None,
                "setting_new": "3/4",
            },
        ),
        redo=True,
        config_path=config_path,
    )
    assert state.piece.bars[0].time_sig == "3/4"
    assert state.settings["time"] == "3/4"
    chords = [Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]
    apply_action(
        state,
        UndoAction(kind="chords", data={"bar": 0, "prev": [], "new": chords}),
        redo=True,
        config_path=config_path,
    )
    assert state.piece.bars[0].chords
    apply_action(
        state,
        UndoAction(kind="bar-insert", data={"index": 1, "prev": set(), "new": {1}}),
        redo=True,
        config_path=config_path,
    )
    assert len(state.piece.bars) == 3
    apply_action(
        state,
        UndoAction(kind="bar-insert", data={"index": 1, "prev": set(), "new": {1}}),
        redo=False,
        config_path=config_path,
    )
    assert len(state.piece.bars) == 2
    apply_action(
        state,
        UndoAction(kind="stave-breaks", data={"prev": set(), "new": {1}}),
        redo=True,
        config_path=config_path,
    )
    assert state.stave_breaks == {1}
    snapshot = snapshot_bar(state, 0)
    apply_action(
        state,
        UndoAction(
            kind="bar-delete",
            data={"index": 0, "snapshot": snapshot, "prev": set(), "new": set()},
        ),
        redo=True,
        config_path=config_path,
    )
    assert len(state.piece.bars) == 1
    apply_action(
        state,
        UndoAction(
            kind="bar-delete",
            data={"index": 0, "snapshot": snapshot, "prev": set(), "new": set()},
        ),
        redo=False,
        config_path=config_path,
    )
    assert len(state.piece.bars) == 2
    apply_action(
        state,
        UndoAction(kind="bar-clear", data={"index": 0, "snapshot": snapshot}),
        redo=True,
        config_path=config_path,
    )
    assert state.piece.bars[0].notes == []


def test_undo_redo_stack(tmp_path: Path) -> None:
    state = _state()
    state.settings["tempo"] = "90"
    action = UndoAction(
        kind="setting",
        data={"key": "tempo", "prev": "90", "new": "120"},
    )
    state.undo_stack.append(action)
    undo(state, config_path=str(tmp_path / "cfg.toml"))
    assert state.settings["tempo"] == "90"
    redo(state, config_path=str(tmp_path / "cfg.toml"))
    assert state.settings["tempo"] == "120"
