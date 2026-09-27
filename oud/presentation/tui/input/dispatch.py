from __future__ import annotations

from oud.editor.core.input.keymap import Action, keymap_for
from oud.editor.core.input.modes import Mode
from oud.editor.core.session import set_mode
from oud.editor.core.state import EditorState
from oud.editor.interaction.prompt.state import (
    command_history_commit,
    command_history_reset_nav,
    search_history_commit,
    search_history_reset_nav,
)
from oud.editor.interaction.prompt.state import command_history_next as command_history_next_state
from oud.editor.interaction.prompt.state import command_history_prev as command_history_prev_state
from oud.presentation.tui.input.completion import complete_command_text
from oud.presentation.tui.prompt import PromptBindings, update_prompt


def prompt_bindings(state: EditorState, mode: Mode) -> PromptBindings:
    """Line-editing keys for a prompt, taken from the key table."""
    keymap = keymap_for(state, mode)
    return PromptBindings(
        escape=keymap.keys_for(Action.PROMPT_CANCEL),
        backspace=keymap.keys_for(Action.PROMPT_BACKSPACE),
        enter=keymap.keys_for(Action.PROMPT_SUBMIT),
        tab=keymap.keys_for(Action.PROMPT_COMPLETE),
        history_up=keymap.keys_for(Action.PROMPT_HISTORY_PREV),
        history_down=keymap.keys_for(Action.PROMPT_HISTORY_NEXT),
    )


def history_prev(state: EditorState) -> str | None:
    return command_history_prev_state(state)


def history_next(state: EditorState) -> str | None:
    return command_history_next_state(state)


def complete_command(state: EditorState) -> bool:
    state.cmdline, message = complete_command_text(state, state.cmdline)
    state.message = message or ""
    return True


def handle_command(state: EditorState, key: int, apply_command) -> bool:
    bindings = prompt_bindings(state, Mode.COMMAND)

    def _complete(text: str) -> tuple[str, str | None]:
        return complete_command_text(state, text)

    result = update_prompt(
        state.cmdline,
        key,
        bindings,
        history=state.command_history,
        history_index=state.command_history_index,
        on_complete=_complete if key in bindings.tab else None,
    )
    if key in bindings.tab:
        state.message = result.message or ""
    elif result.message:
        state.message = result.message
    state.cmdline = result.text
    state.command_history_index = result.history_index
    if result.cancel:
        set_mode(state, Mode.NORMAL)
        state.cmdline = ""
        state.message = ""
        command_history_reset_nav(state)
        return True
    if result.submit:
        cmd = state.cmdline
        state.cmdline = ""
        set_mode(state, Mode.NORMAL)
        command_history_commit(state, cmd)
        apply_command(state, cmd)
        return True
    return True


def parse_search(text: str) -> int | None:
    text = text.strip()
    if not text or not text.isdigit():
        return None
    value = int(text)
    return value - 1 if value > 0 else None


def handle_search(state: EditorState, key: int) -> bool:
    bindings = prompt_bindings(state, Mode.SEARCH)
    result = update_prompt(
        state.searchline,
        key,
        bindings,
        history=state.search_history,
        history_index=state.search_history_index,
    )
    state.searchline = result.text
    state.search_history_index = result.history_index
    if result.cancel:
        set_mode(state, Mode.NORMAL)
        state.searchline = ""
        search_history_reset_nav(state)
        return True
    if result.submit:
        search_text = state.searchline
        target = parse_search(search_text)
        state.searchline = ""
        set_mode(state, Mode.NORMAL)
        search_history_commit(state, search_text)
        if target is None:
            state.message = "Invalid bar"
            return True
        state.cursor_bar = max(0, min(target, len(state.piece.bars) - 1))
        state.cursor_col = 0
        return True
    return True
