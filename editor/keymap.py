from __future__ import annotations

from dataclasses import dataclass

from editor.controller_utils import allow_arrows, is_casual


@dataclass(frozen=True)
class KeyProfile:
    move_left: tuple[int, ...]
    move_right: tuple[int, ...]
    move_up: tuple[int, ...]
    move_down: tuple[int, ...]
    help_extra: tuple[int, ...]
    bar_after_extra: tuple[int, ...]
    bar_delete_extra: tuple[int, ...]
    bar_next: tuple[int, ...]
    bar_prev: tuple[int, ...]
    page_up: tuple[int, ...]
    page_down: tuple[int, ...]
    col_start: tuple[int, ...]
    col_end: tuple[int, ...]


def _profile(state) -> KeyProfile:
    keycodes = state.keycodes
    if is_casual(state):
        return KeyProfile(
            move_left=(ord("a"),),
            move_right=(ord("d"),),
            move_up=(ord("w"),),
            move_down=(ord("s"),),
            help_extra=(keycodes.f1,),
            bar_after_extra=(keycodes.ic,),
            bar_delete_extra=(keycodes.dc,),
            bar_next=(ord("."),),
            bar_prev=(ord(","),),
            page_up=(keycodes.ppage,),
            page_down=(keycodes.npage,),
            col_start=(keycodes.home,),
            col_end=(keycodes.end,),
        )
    return KeyProfile(
        move_left=(ord("h"),),
        move_right=(ord("l"),),
        move_up=(ord("k"),),
        move_down=(ord("j"),),
        help_extra=(),
        bar_after_extra=(),
        bar_delete_extra=(),
        bar_next=(ord("w"),),
        bar_prev=(ord("b"),),
        page_up=(ord("K"), ord("{")),
        page_down=(ord("J"), ord("}")),
        col_start=(),
        col_end=(ord("e"), ord("$")),
    )


@dataclass(frozen=True)
class MovementKeys:
    left: tuple[int, ...]
    right: tuple[int, ...]
    up: tuple[int, ...]
    down: tuple[int, ...]


@dataclass(frozen=True)
class NormalBindings:
    quit: tuple[int, ...]
    command: tuple[int, ...]
    help: tuple[int, ...]
    search: tuple[int, ...]
    insert: tuple[int, ...]
    replace: tuple[int, ...]
    info: tuple[int, ...]
    bar_after: tuple[int, ...]
    bar_before: tuple[int, ...]
    bar_delete: tuple[int, ...]
    print_pdf: tuple[int, ...]
    play: tuple[int, ...]
    undo: tuple[int, ...]
    redo: tuple[int, ...]


@dataclass(frozen=True)
class InsertBindings:
    quit: tuple[int, ...]
    escape: tuple[int, ...]
    clear: tuple[int, ...]
    barline: tuple[int, ...]
    dot: tuple[int, ...]
    prefix: tuple[int, ...]


@dataclass(frozen=True)
class CommandBindings:
    escape: tuple[int, ...]
    tab: tuple[int, ...]
    backspace: tuple[int, ...]
    history_up: tuple[int, ...]
    history_down: tuple[int, ...]
    enter: tuple[int, ...]


@dataclass(frozen=True)
class SearchBindings:
    escape: tuple[int, ...]
    backspace: tuple[int, ...]
    enter: tuple[int, ...]


@dataclass(frozen=True)
class HelpBindings:
    exit: tuple[int, ...]
    up: tuple[int, ...]
    down: tuple[int, ...]


@dataclass(frozen=True)
class CountBindings:
    digits: tuple[int, ...]
    zero: int


@dataclass(frozen=True)
class NormalActionBindings:
    row_first: tuple[int, ...]
    delete_cell: tuple[int, ...]
    paste: tuple[int, ...]
    pending: tuple[int, ...]
    bar_next: tuple[int, ...]
    bar_prev: tuple[int, ...]
    page_up: tuple[int, ...]
    page_down: tuple[int, ...]
    col_start: tuple[int, ...]
    col_end: tuple[int, ...]
    jump_bottom: tuple[int, ...]


@dataclass(frozen=True)
class PendingBindings:
    gg: tuple[int, ...]
    gj: tuple[int, ...]
    gp: tuple[int, ...]
    dd: tuple[int, ...]
    yy: tuple[int, ...]


@dataclass(frozen=True)
class PluginBindings:
    exit: tuple[int, ...]
    back: tuple[int, ...]
    up: tuple[int, ...]
    down: tuple[int, ...]
    open: tuple[int, ...]
    download: tuple[int, ...]
    search: tuple[int, ...]
    prefix: tuple[int, ...]
    bottom: tuple[int, ...]
    enter: tuple[int, ...]
    backspace: tuple[int, ...]
    escape: tuple[int, ...]


@dataclass(frozen=True)
class HelpActionBindings:
    viewer: tuple[int, ...]


def movement_keys(state, *, include_arrows: bool) -> MovementKeys:
    profile = _profile(state)
    left = profile.move_left
    right = profile.move_right
    up = profile.move_up
    down = profile.move_down
    if include_arrows and allow_arrows(state):
        keycodes = state.keycodes
        left += (keycodes.left,)
        right += (keycodes.right,)
        up += (keycodes.up,)
        down += (keycodes.down,)
    return MovementKeys(left=left, right=right, up=up, down=down)


def normal_bindings(state) -> NormalBindings:
    keycodes = state.keycodes
    profile = _profile(state)
    help_keys: tuple[int, ...] = (ord("?"), *profile.help_extra)
    bar_after: tuple[int, ...] = (ord("o"), ord("+"), *profile.bar_after_extra)
    bar_delete: tuple[int, ...] = (ord("X"), ord("-"), *profile.bar_delete_extra)
    return NormalBindings(
        quit=(ord("q"), ord("Q"), 3),
        command=(ord(":"),),
        help=help_keys,
        search=(ord("/"),),
        insert=(ord("i"), keycodes.enter, 10, 13),
        replace=(ord("r"),),
        info=(ord("I"),),
        bar_after=bar_after,
        bar_before=(ord("O"),),
        bar_delete=bar_delete,
        print_pdf=(ord("P"),),
        play=(ord("m"), ord("M")),
        undo=(ord("u"),),
        redo=(18,),
    )


def insert_bindings(state) -> InsertBindings:
    keycodes = state.keycodes
    return InsertBindings(
        quit=(ord("q"), ord("Q"), 3),
        escape=(27, keycodes.exit),
        clear=(ord(" "), keycodes.backspace, 127, 8),
        barline=(ord("|"),),
        dot=(ord("."),),
        prefix=(ord(";"),),
    )


def command_bindings(state) -> CommandBindings:
    keycodes = state.keycodes
    key_tab = keycodes.tab or 9
    return CommandBindings(
        escape=(27,),
        tab=(key_tab, 9),
        backspace=(keycodes.backspace, 127, 8),
        history_up=(keycodes.up,),
        history_down=(keycodes.down,),
        enter=(keycodes.enter, 10, 13),
    )


def search_bindings(state) -> SearchBindings:
    keycodes = state.keycodes
    return SearchBindings(
        escape=(27,),
        backspace=(keycodes.backspace, 127, 8),
        enter=(keycodes.enter, 10, 13),
    )


def help_bindings() -> HelpBindings:
    return HelpBindings(
        exit=(ord("q"), ord("Q"), 27),
        up=(ord("k"),),
        down=(ord("j"),),
    )


def count_bindings() -> CountBindings:
    digits = tuple(ord(ch) for ch in "0123456789")
    return CountBindings(digits=digits, zero=ord("0"))


def normal_action_bindings(state) -> NormalActionBindings:
    profile = _profile(state)
    bar_next = profile.bar_next
    bar_prev = profile.bar_prev
    page_up = profile.page_up
    page_down = profile.page_down
    col_start = profile.col_start
    col_end = profile.col_end
    return NormalActionBindings(
        row_first=(ord("^"),),
        delete_cell=(ord("x"),),
        paste=(ord("p"),),
        pending=(ord("g"), ord("d"), ord("y")),
        bar_next=bar_next,
        bar_prev=bar_prev,
        page_up=page_up,
        page_down=page_down,
        col_start=col_start,
        col_end=col_end,
        jump_bottom=(ord("G"),),
    )


def pending_bindings() -> PendingBindings:
    return PendingBindings(
        gg=(ord("g"),),
        gj=(ord("j"),),
        gp=(ord("p"),),
        dd=(ord("d"),),
        yy=(ord("y"),),
    )


def italian_duration_digits() -> tuple[int, ...]:
    return tuple(ord(ch) for ch in "1234567")


def help_action_bindings() -> HelpActionBindings:
    return HelpActionBindings(viewer=(ord("?"),))


def plugin_bindings(state) -> PluginBindings:
    keycodes = state.keycodes
    return PluginBindings(
        exit=(ord("q"), ord("Q"), 27, keycodes.exit, ord("b")),
        back=(ord("h"), keycodes.left),
        up=(ord("k"), keycodes.up),
        down=(ord("j"), keycodes.down),
        open=(ord("l"), keycodes.enter, 10, 13),
        download=(ord("d"),),
        search=(ord("/"),),
        prefix=(ord("g"),),
        bottom=(ord("G"),),
        enter=(keycodes.enter, 10, 13),
        backspace=(keycodes.backspace, 127, 8),
        escape=(27, keycodes.exit),
    )
