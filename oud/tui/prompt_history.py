from __future__ import annotations


def history_prev(
    history: list[str],
    history_index: int | None,
) -> tuple[str | None, int | None]:
    if not history:
        return None, history_index
    new_index = len(history) - 1 if history_index is None else max(0, history_index - 1)
    return history[new_index], new_index


def history_next(
    history: list[str],
    history_index: int | None,
) -> tuple[str | None, int | None]:
    if not history:
        return None, history_index
    if history_index is None:
        return "", None
    new_index = min(len(history), history_index + 1)
    if new_index >= len(history):
        return "", None
    return history[new_index], new_index
