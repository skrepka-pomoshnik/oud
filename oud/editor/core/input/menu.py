from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


def menu_page_size(screen_height: int, *, reserved_rows: int = 2) -> int:
    return max(1, screen_height - reserved_rows)


def menu_clamp_index(index: int, length: int) -> int:
    if length <= 0:
        return 0
    return max(0, min(index, length - 1))


def menu_sync_offset(index: int, offset: int, page_size: int, length: int) -> int:
    if length <= 0:
        return 0
    index = menu_clamp_index(index, length)
    offset = max(0, offset)
    offset = min(offset, index)
    if index >= offset + page_size:
        offset = index - page_size + 1
    return max(0, min(offset, max(0, length - 1)))


def menu_move_down(
    index: int,
    offset: int,
    length: int,
    page_size: int,
    *,
    step: int = 1,
) -> tuple[int, int]:
    if length <= 0:
        return 0, 0
    new_index = menu_clamp_index(index + max(1, step), length)
    new_offset = menu_sync_offset(new_index, offset, page_size, length)
    return new_index, new_offset


def menu_move_up(
    index: int,
    offset: int,
    length: int,
    page_size: int,
    *,
    step: int = 1,
) -> tuple[int, int]:
    if length <= 0:
        return 0, 0
    new_index = menu_clamp_index(index - max(1, step), length)
    new_offset = menu_sync_offset(new_index, offset, page_size, length)
    return new_index, new_offset


def menu_jump_top(length: int) -> tuple[int, int]:
    if length <= 0:
        return 0, 0
    return 0, 0


def menu_jump_bottom(length: int, page_size: int) -> tuple[int, int]:
    if length <= 0:
        return 0, 0
    index = length - 1
    offset = max(0, index - page_size + 1)
    return index, offset


def menu_find_index(items: list[T], query: str, text_fn: Callable[[T], str]) -> int | None:
    needle = query.strip().lower()
    if not needle:
        return None
    for idx, item in enumerate(items):
        if needle in text_fn(item).lower():
            return idx
    return None


def menu_scroll_offset(offset: int, delta: int) -> int:
    return max(0, offset + delta)


@dataclass(frozen=True)
class MenuNavBindings:
    up: tuple[int, ...]
    down: tuple[int, ...]
    top_prefix: tuple[int, ...]
    bottom: tuple[int, ...]


@dataclass(frozen=True)
class MenuNavState:
    index: int = 0
    offset: int = 0
    pending_prefix: str = ""


def menu_reduce_nav(
    key: int,
    nav: MenuNavState,
    *,
    bindings: MenuNavBindings,
    length: int,
    page_size: int,
) -> tuple[MenuNavState, bool]:
    result: tuple[MenuNavState, bool] | None = None
    if key in bindings.top_prefix:
        if nav.pending_prefix == "g":
            index, offset = menu_jump_top(length)
            result = MenuNavState(index=index, offset=offset, pending_prefix=""), True
        else:
            result = (
                MenuNavState(
                    index=nav.index,
                    offset=nav.offset,
                    pending_prefix="g",
                ),
                True,
            )
    elif key in bindings.bottom:
        index, offset = menu_jump_bottom(length, page_size)
        result = MenuNavState(index=index, offset=offset, pending_prefix=""), True
    elif key in bindings.down:
        index, offset = menu_move_down(nav.index, nav.offset, length, page_size)
        result = MenuNavState(index=index, offset=offset, pending_prefix=""), True
    elif key in bindings.up:
        index, offset = menu_move_up(nav.index, nav.offset, length, page_size)
        result = MenuNavState(index=index, offset=offset, pending_prefix=""), True
    elif nav.pending_prefix:
        result = (
            MenuNavState(
                index=nav.index,
                offset=nav.offset,
                pending_prefix="",
            ),
            False,
        )
    return (nav, False) if result is None else result
