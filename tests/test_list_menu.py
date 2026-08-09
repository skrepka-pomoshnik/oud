from oud.editor.core.input.menu import (
    MenuNavBindings,
    MenuNavState,
    menu_find_index,
    menu_jump_bottom,
    menu_jump_top,
    menu_move_down,
    menu_move_up,
    menu_page_size,
    menu_reduce_nav,
    menu_scroll_offset,
    menu_sync_offset,
)


def test_menu_navigation_and_offset_sync() -> None:
    index, offset = 0, 0
    page_size = 3
    length = 7
    index, offset = menu_move_down(index, offset, length, page_size)
    assert (index, offset) == (1, 0)
    index, offset = menu_move_down(index, offset, length, page_size, step=2)
    assert (index, offset) == (3, 1)
    index, offset = menu_move_up(index, offset, length, page_size)
    assert (index, offset) == (2, 1)
    assert menu_sync_offset(6, 0, page_size, length) == 4


def test_menu_top_bottom_jumps() -> None:
    assert menu_jump_top(5) == (0, 0)
    assert menu_jump_bottom(5, 3) == (4, 2)
    assert menu_jump_bottom(0, 3) == (0, 0)


def test_menu_find_index_and_scroll_offset() -> None:
    items = ["alpha", "beta", "gamma"]
    assert menu_find_index(items, "mm", str) == 2
    assert menu_find_index(items, "zzz", str) is None
    assert menu_scroll_offset(3, -10) == 0
    assert menu_scroll_offset(3, 2) == 5
    assert menu_page_size(10) == 8


def test_menu_reduce_nav_handles_prefix_and_motion() -> None:
    bindings = MenuNavBindings(
        up=(ord("k"),),
        down=(ord("j"),),
        top_prefix=(ord("g"),),
        bottom=(ord("G"),),
    )
    nav = MenuNavState(index=0, offset=0, pending_prefix="")
    nav, handled = menu_reduce_nav(
        ord("j"),
        nav,
        bindings=bindings,
        length=6,
        page_size=3,
    )
    assert handled is True
    assert nav.index == 1
    nav, handled = menu_reduce_nav(
        ord("g"),
        nav,
        bindings=bindings,
        length=6,
        page_size=3,
    )
    assert handled is True
    assert nav.pending_prefix == "g"
    nav, handled = menu_reduce_nav(
        ord("g"),
        nav,
        bindings=bindings,
        length=6,
        page_size=3,
    )
    assert handled is True
    assert nav.index == 0
    nav, handled = menu_reduce_nav(
        ord("G"),
        nav,
        bindings=bindings,
        length=6,
        page_size=3,
    )
    assert handled is True
    assert nav.index == 5
