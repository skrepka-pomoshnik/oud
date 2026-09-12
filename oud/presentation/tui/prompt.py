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


def _prompt_action(key: int, bindings: PromptBindings, has_completion: bool) -> str | None:
    actions = (
        ("escape", bindings.escape),
        ("tab", bindings.tab if has_completion else ()),
        ("backspace", bindings.backspace),
        ("history_up", bindings.history_up),
        ("history_down", bindings.history_down),
        ("enter", bindings.enter),
    )
    return next((name for name, keys in actions if key in keys), None)


def _history_prompt_result(
    text: str,
    history: list[str],
    history_index: int | None,
    *,
    direction: int,
) -> PromptResult:
    if not history:
        return PromptResult(text, history_index)
    if direction < 0:
        index = len(history) - 1 if history_index is None else max(0, history_index - 1)
        return PromptResult(history[index], index)
    if history_index is None:
        return PromptResult(text, history_index)
    index = min(len(history), history_index + 1)
    if index >= len(history):
        return PromptResult("", None)
    return PromptResult(history[index], index)


def _printable_prompt_result(text: str, history_index: int | None, key: int) -> PromptResult:
    if ord(" ") <= key <= ord("~"):
        return PromptResult(text + chr(key), history_index)
    return PromptResult(text, history_index)


def update_prompt(
    text: str,
    key: int,
    bindings: PromptBindings,
    *,
    history: list[str],
    history_index: int | None,
    on_complete: Callable[[str], tuple[str, str | None]] | None = None,
) -> PromptResult:
    action = _prompt_action(key, bindings, on_complete is not None)
    if action == "escape":
        return PromptResult("", None, cancel=True)
    if action == "tab" and on_complete is not None:
        new_text, message = on_complete(text)
        return PromptResult(new_text, history_index, message=message)
    if action == "backspace":
        return PromptResult(text[:-1], history_index)
    if action in {"history_up", "history_down"}:
        direction = -1 if action == "history_up" else 1
        return _history_prompt_result(text, history, history_index, direction=direction)
    if action == "enter":
        return PromptResult(text, history_index, submit=True)
    return _printable_prompt_result(text, history_index, key)
