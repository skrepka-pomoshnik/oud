from __future__ import annotations

from oud.editor.core.input.keymap import command_bindings, search_bindings
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


def _prompt_bindings(bindings) -> PromptBindings:
    return PromptBindings(
        escape=bindings.escape,
        backspace=bindings.backspace,
        enter=bindings.enter,
        tab=getattr(bindings, "tab", ()),
        history_up=getattr(bindings, "history_up", ()),
        history_down=getattr(bindings, "history_down", ()),
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
    bindings = command_bindings(state)
    prompt_bindings = _prompt_bindings(bindings)

    def _complete(text: str) -> tuple[str, str | None]:
        return complete_command_text(state, text)

    result = update_prompt(
        state.cmdline,
        key,
        prompt_bindings,
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
        set_mode(state, "normal")
        state.cmdline = ""
        command_history_reset_nav(state)
        return True
    if result.submit:
        cmd = state.cmdline
        state.cmdline = ""
        set_mode(state, "normal")
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
    bindings = search_bindings(state)
    prompt_bindings = _prompt_bindings(bindings)
    result = update_prompt(
        state.searchline,
        key,
        prompt_bindings,
        history=state.search_history,
        history_index=state.search_history_index,
    )
    state.searchline = result.text
    state.search_history_index = result.history_index
    if result.cancel:
        set_mode(state, "normal")
        state.searchline = ""
        search_history_reset_nav(state)
        return True
    if result.submit:
        search_text = state.searchline
        target = parse_search(search_text)
        state.searchline = ""
        set_mode(state, "normal")
        search_history_commit(state, search_text)
        if target is None:
            state.message = "Invalid bar"
            return True
        state.cursor_bar = max(0, min(target, len(state.piece.bars) - 1))
        state.cursor_col = 0
        return True
    return True
