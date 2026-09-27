from __future__ import annotations

from oud.editor.core.feedback.transient import (
    DEFAULT_MESSAGE_TTL_TICKS,
    decay_transient_message,
)
from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from petrucci.core.model import Bar, Piece


def _state() -> EditorState:
    return EditorState(
        Piece(title="T", bars=[Bar()], strings=6),
        settings={"style": "french"},
    )


def test_message_assignment_sets_default_ttl() -> None:
    state = _state()
    state.message = "Saved"
    assert state.message == "Saved"
    assert state.message_ttl_ticks == DEFAULT_MESSAGE_TTL_TICKS
    state.message = ""
    assert state.message_ttl_ticks == 0


def test_decay_transient_message_expires_only_after_ttl() -> None:
    state = _state()
    state.mode = Mode.NORMAL
    state.message = "Saved"
    state.message_ttl_ticks = 2
    assert decay_transient_message(state) is True
    assert state.message == "Saved"
    assert state.message_ttl_ticks == 1
    assert decay_transient_message(state) is True
    assert state.message == ""
    assert state.message_ttl_ticks == 0


def test_decay_transient_message_skips_command_and_search_modes() -> None:
    for mode in ("command", "search", "help", "plugin"):
        state = _state()
        state.mode = Mode(mode)
        state.message = "Saved"
        state.message_ttl_ticks = 1
        assert decay_transient_message(state) is False
        assert state.message == "Saved"
        assert state.message_ttl_ticks == 1


def test_decay_transient_message_clears_stale_zero_ttl_message() -> None:
    state = _state()
    state.mode = Mode.INSERT
    state.message = "Saved"
    state.message_ttl_ticks = 0
    assert decay_transient_message(state) is True
    assert state.message == ""
    assert state.message_ttl_ticks == 0
