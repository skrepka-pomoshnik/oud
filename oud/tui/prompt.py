from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptBindings:
    escape: tuple[int, ...]
    backspace: tuple[int, ...]
    enter: tuple[int, ...]
    tab: tuple[int, ...]
    history_up: tuple[int, ...]
    history_down: tuple[int, ...]


@dataclass(frozen=True)
class PromptResult:
    text: str
    history_index: int | None
    submit: bool = False
    cancel: bool = False
    message: str | None = None


def update_prompt(  # noqa: C901, PLR0911
    text: str,
    key: int,
    bindings: PromptBindings,
    *,
    history: list[str],
    history_index: int | None,
    on_complete: Callable[[str], tuple[str, str | None]] | None = None,
) -> PromptResult:
    if key in bindings.escape:
        return PromptResult("", None, cancel=True)
    if key in bindings.tab and on_complete is not None:
        new_text, message = on_complete(text)
        return PromptResult(new_text, history_index, message=message)
    if key in bindings.backspace:
        return PromptResult(text[:-1], history_index)
    if key in bindings.history_up:
        if not history:
            return PromptResult(text, history_index)
        history_index = len(history) - 1 if history_index is None else max(0, history_index - 1)
        return PromptResult(history[history_index], history_index)
    if key in bindings.history_down:
        if not history:
            return PromptResult(text, history_index)
        if history_index is None:
            return PromptResult(text, history_index)
        history_index = min(len(history), history_index + 1)
        if history_index >= len(history):
            return PromptResult("", None)
        return PromptResult(history[history_index], history_index)
    if key in bindings.enter:
        return PromptResult(text, history_index, submit=True)
    if 32 <= key <= 126:
        return PromptResult(text + chr(key), history_index)
    return PromptResult(text, history_index)
