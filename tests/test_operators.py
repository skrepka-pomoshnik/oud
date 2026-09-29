from __future__ import annotations

from pathlib import Path

from oud.editor.core.feedback.messages import READ_ONLY_VIEWER
from oud.editor.core.input.keycodes import DEFAULT_KEYCODES
from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from oud.editor.services.bootstrap import init_state
from tests.helpers_ft3 import write_galliard
from tests.helpers_keyscript import press_keys

ESC = 27
CTRL_X = 24


def _state(tmp_path: Path, keys: str = "vim") -> EditorState:
    state = init_state(str(write_galliard(tmp_path)), config_path=str(tmp_path / "config.toml"))
    state.settings["keys"] = keys
    state.screen_width = 120
    return state


def _notes(state: EditorState) -> list[list[list[tuple[int, int]]]]:
    return [[[(n.string, n.fret) for n in chord.notes] for chord in bar.chords] for bar in state.piece.bars]


def test_operator_delete_over_a_motion_matches_the_visual_selection(tmp_path: Path) -> None:
    operator = _state(tmp_path)
    visual = _state(tmp_path)

    press_keys(operator, ["d", "l"])
    press_keys(visual, ["v", "l", "d"])

    assert _notes(operator) == _notes(visual)
    assert _notes(operator) != _notes(_state(tmp_path))
    assert operator.mode == Mode.NORMAL


def test_operator_and_motion_counts_multiply(tmp_path: Path) -> None:
    twice_two = _state(tmp_path)
    four = _state(tmp_path)

    press_keys(twice_two, ["2", "d", "2", "l"])
    press_keys(four, ["d", "4", "l"])

    assert _notes(twice_two) == _notes(four)


def test_doubled_operator_cuts_counted_bars(tmp_path: Path) -> None:
    state = _state(tmp_path)
    bars = len(state.piece.bars)

    press_keys(state, ["2", "d", "d"])

    assert len(state.piece.bars) == bars - 2
    assert state.yanked_bars is not None
    assert len(state.yanked_bars) == 2


def test_doubled_yank_copies_bars_and_paste_restores_them(tmp_path: Path) -> None:
    state = _state(tmp_path)
    bars = len(state.piece.bars)

    press_keys(state, ["y", "y", "p"])

    assert len(state.piece.bars) == bars + 1


def test_yank_over_a_motion_keeps_the_score(tmp_path: Path) -> None:
    state = _state(tmp_path)
    before = _notes(state)

    press_keys(state, ["y", "l"])

    assert _notes(state) == before
    assert state.mode == Mode.NORMAL
    assert state.yanked_rows


def test_change_operator_deletes_then_enters_insert_mode(tmp_path: Path) -> None:
    state = _state(tmp_path)

    press_keys(state, ["c", "l"])

    assert state.mode == Mode.INSERT


def test_operator_with_a_failed_find_changes_nothing(tmp_path: Path) -> None:
    state = _state(tmp_path)
    before = _notes(state)

    press_keys(state, ["d", "f", "z"])

    assert _notes(state) == before
    assert state.mode == Mode.NORMAL
    assert state.pending_operator is None


def test_escape_cancels_a_pending_operator(tmp_path: Path) -> None:
    state = _state(tmp_path)
    before = _notes(state)

    press_keys(state, ["d", ESC, "l"])

    assert state.pending_operator is None
    assert _notes(state) == before


def test_operator_refuses_in_a_read_only_score(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.read_only = True

    press_keys(state, ["d", "d"])

    assert state.message == READ_ONLY_VIEWER
    assert state.pending_operator is None


def test_yank_operator_works_in_a_read_only_score(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.read_only = True

    press_keys(state, ["y", "y"])

    assert state.yanked_bars


def test_dot_repeats_the_last_bar_cut(tmp_path: Path) -> None:
    state = _state(tmp_path)
    bars = len(state.piece.bars)

    press_keys(state, ["d", "d", "."])

    assert len(state.piece.bars) == bars - 2


def test_dot_repeats_a_delete_over_a_motion(tmp_path: Path) -> None:
    once = _state(tmp_path)
    repeated = _state(tmp_path)

    press_keys(once, ["d", "l", "d", "l"])
    press_keys(repeated, ["d", "l", "."])

    assert _notes(repeated) == _notes(once)


def test_dot_repeats_a_bar_insert(tmp_path: Path) -> None:
    state = _state(tmp_path)
    bars = len(state.piece.bars)

    press_keys(state, ["o", "."])

    assert len(state.piece.bars) == bars + 2


def test_dot_takes_a_new_count_for_the_repeated_edit(tmp_path: Path) -> None:
    repeated = _state(tmp_path)
    direct = _state(tmp_path)

    press_keys(repeated, ["x", "2", "."])
    press_keys(direct, ["x", "2", "x"])

    assert _notes(repeated) == _notes(direct)


def test_dot_without_an_edit_says_so(tmp_path: Path) -> None:
    state = _state(tmp_path)

    press_keys(state, ["."])

    assert state.message == "Nothing to repeat"


def test_dot_is_undone_as_one_step(tmp_path: Path) -> None:
    state = _state(tmp_path)
    before = _notes(state)

    press_keys(state, ["d", "l", "u"])

    assert _notes(state) == before


def test_casual_profile_has_the_same_operators(tmp_path: Path) -> None:
    casual = _state(tmp_path, keys="casual")
    vim = _state(tmp_path)
    bars = len(casual.piece.bars)

    press_keys(casual, [CTRL_X, CTRL_X])
    press_keys(vim, ["d", "d"])
    assert len(casual.piece.bars) == bars - 1
    assert _notes(casual) == _notes(vim)

    press_keys(casual, [DEFAULT_KEYCODES.f4])
    assert len(casual.piece.bars) == bars - 2


def test_casual_operator_takes_its_motion_from_wasd(tmp_path: Path) -> None:
    casual = _state(tmp_path, keys="casual")
    vim = _state(tmp_path)

    press_keys(casual, [CTRL_X, "d"])
    press_keys(vim, ["d", "l"])

    assert _notes(casual) == _notes(vim)


def test_casual_reverse_find_repeat_uses_backslash(tmp_path: Path) -> None:
    casual = _state(tmp_path, keys="casual")
    vim = _state(tmp_path)

    press_keys(casual, ["f", "a", ";", "\\"])
    press_keys(vim, ["f", "a", ";", ","])

    assert (casual.cursor_bar, casual.cursor_onset, casual.cursor_string) == (
        vim.cursor_bar,
        vim.cursor_onset,
        vim.cursor_string,
    )
