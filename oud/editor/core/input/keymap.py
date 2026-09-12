from __future__ import annotations

from dataclasses import dataclass

from oud.editor.core.coordinates import allow_arrows, is_casual


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
    scroll_up: tuple[int, ...]
    scroll_down: tuple[int, ...]
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
            page_up=(ord("W"),),
            page_down=(ord("S"),),
            scroll_up=(keycodes.ppage,),
            scroll_down=(keycodes.npage,),
            col_start=(keycodes.home,),
            col_end=(keycodes.end,),
        )
    return KeyProfile(
        move_left=(ord("h"), 2),  # h, Ctrl-B
        move_right=(ord("l"), 6),  # l, Ctrl-F
        move_up=(ord("k"), 16),  # k, Ctrl-P
        move_down=(ord("j"), 14),  # j, Ctrl-N
        help_extra=(),
        bar_after_extra=(),
        bar_delete_extra=(),
        bar_next=(ord("w"),),
        bar_prev=(ord("b"),),
        page_up=(ord("K"), ord("{")),
        page_down=(ord("J"), ord("}")),
        scroll_up=(keycodes.ppage, 21),  # PgUp, Ctrl-U
        scroll_down=(keycodes.npage, 4),  # PgDn, Ctrl-D
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
    history_up: tuple[int, ...]
    history_down: tuple[int, ...]


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
    scroll_up: tuple[int, ...]
    scroll_down: tuple[int, ...]
    section_prev: tuple[int, ...]
    section_next: tuple[int, ...]
    col_start: tuple[int, ...]
    col_end: tuple[int, ...]
    jump_bottom: tuple[int, ...]
    find_forward: tuple[int, ...]
    find_backward: tuple[int, ...]
    till_forward: tuple[int, ...]
    till_backward: tuple[int, ...]
    find_repeat: tuple[int, ...]
    find_repeat_reverse: tuple[int, ...]
    word_search_forward: tuple[int, ...]
    word_search_backward: tuple[int, ...]
    word_search_next: tuple[int, ...]
    word_search_prev: tuple[int, ...]
    match_jump: tuple[int, ...]
    mark_set: tuple[int, ...]
    mark_jump_line: tuple[int, ...]
    mark_jump_exact: tuple[int, ...]


@dataclass(frozen=True)
class PendingBindings:
    gg: tuple[int, ...]
    gh: tuple[int, ...]
    gj: tuple[int, ...]
    gi: tuple[int, ...]
    gp: tuple[int, ...]
    gr: tuple[int, ...]
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
    download_tree: tuple[int, ...]
    search: tuple[int, ...]
    prefix: tuple[int, ...]
    bottom: tuple[int, ...]
    enter: tuple[int, ...]
    backspace: tuple[int, ...]
    escape: tuple[int, ...]


@dataclass(frozen=True)
class HelpActionBindings:
    viewer: tuple[int, ...]


def _parse_key_token(state, token: str) -> int | None:
    keycodes = state.keycodes
    text = token.strip()
    result: int | None = None
    if text:
        lower = text.lower()
        named = {
            "left": keycodes.left,
            "right": keycodes.right,
            "up": keycodes.up,
            "down": keycodes.down,
            "home": keycodes.home,
            "end": keycodes.end,
            "pgup": keycodes.ppage,
            "pageup": keycodes.ppage,
            "pgdn": keycodes.npage,
            "pagedown": keycodes.npage,
            "enter": keycodes.enter,
            "return": keycodes.enter,
            "esc": 27,
            "escape": 27,
            "tab": keycodes.tab,
            "backspace": keycodes.backspace,
            "delete": keycodes.dc,
            "space": ord(" "),
        }
        if lower in named:
            result = named[lower]
        elif (lower.startswith("ctrl-") and len(lower) == len("ctrl-x") and lower[-1].isalpha()) or (
            lower.startswith("^") and len(lower) == len("^x") and lower[-1].isalpha()
        ):
            result = ord(lower[-1].upper()) & 31
        elif text.isdigit():
            result = int(text)
        elif len(text) == 1:
            result = ord(text)
    return result


def _remap_tuple(state, setting_key: str, default: tuple[int, ...]) -> tuple[int, ...]:
    value = state.settings.get(setting_key, "").strip()
    if not value:
        return default
    parsed: list[int] = []
    for part in value.replace(",", " ").split():
        key = _parse_key_token(state, part)
        if key is not None:
            parsed.append(key)
    return tuple(parsed) if parsed else default


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
    left = _remap_tuple(state, "remap_move_left", left)
    right = _remap_tuple(state, "remap_move_right", right)
    up = _remap_tuple(state, "remap_move_up", up)
    down = _remap_tuple(state, "remap_move_down", down)
    return MovementKeys(left=left, right=right, up=up, down=down)


def normal_bindings(state) -> NormalBindings:
    keycodes = state.keycodes
    profile = _profile(state)
    help_keys: tuple[int, ...] = (ord("?"), *profile.help_extra)
    bar_after: tuple[int, ...] = (ord("o"), ord("+"), *profile.bar_after_extra)
    bar_delete: tuple[int, ...] = (ord("X"), ord("-"), *profile.bar_delete_extra)
    undo = (ord("u"), 26) if is_casual(state) else (ord("u"),)
    redo = (18, 25) if is_casual(state) else (18,)
    return NormalBindings(
        quit=_remap_tuple(state, "remap_quit", (ord("q"), ord("Q"), 3)),
        command=_remap_tuple(state, "remap_command", (ord(":"),)),
        help=_remap_tuple(state, "remap_help", help_keys),
        search=_remap_tuple(state, "remap_search", (ord("/"),)),
        insert=_remap_tuple(state, "remap_insert", (ord("i"), keycodes.enter, 10, 13)),
        replace=_remap_tuple(state, "remap_replace", (ord("r"),)),
        info=_remap_tuple(state, "remap_info", (ord("I"),)),
        bar_after=_remap_tuple(state, "remap_bar_after", bar_after),
        bar_before=_remap_tuple(state, "remap_bar_before", (ord("O"),)),
        bar_delete=_remap_tuple(state, "remap_bar_delete", bar_delete),
        print_pdf=_remap_tuple(state, "remap_print_pdf", (ord("P"),)),
        play=_remap_tuple(state, "remap_play", (ord("M"),)),
        undo=_remap_tuple(state, "remap_undo", undo),
        redo=_remap_tuple(state, "remap_redo", redo),
    )


def insert_bindings(state) -> InsertBindings:
    keycodes = state.keycodes
    return InsertBindings(
        quit=_remap_tuple(state, "remap_insert_quit", (ord("q"), ord("Q"), 3)),
        escape=_remap_tuple(state, "remap_insert_escape", (27, keycodes.exit)),
        clear=_remap_tuple(state, "remap_insert_clear", (ord(" "),)),
        barline=_remap_tuple(state, "remap_insert_barline", (ord("|"),)),
        dot=_remap_tuple(state, "remap_insert_dot", (ord("."),)),
        prefix=_remap_tuple(state, "remap_insert_prefix", (ord(";"), ord(","))),
    )


def command_bindings(state) -> CommandBindings:
    keycodes = state.keycodes
    key_tab = keycodes.tab or 9
    return CommandBindings(
        escape=(27,),
        tab=(key_tab, 9, 1),
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
        history_up=(keycodes.up,),
        history_down=(keycodes.down,),
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
    scroll_up = profile.scroll_up
    scroll_down = profile.scroll_down
    col_start = profile.col_start
    col_end = profile.col_end
    pending = (ord("g"), ord("y")) if is_casual(state) else (ord("g"), ord("d"), ord("y"))
    find_repeat = (ord(";"), ord("]")) if is_casual(state) else (ord(";"),)
    find_repeat_reverse = (ord("["),) if is_casual(state) else (ord(","),)
    return NormalActionBindings(
        row_first=_remap_tuple(state, "remap_row_first", (ord("^"),)),
        delete_cell=_remap_tuple(state, "remap_delete_cell", (ord("x"),)),
        paste=_remap_tuple(state, "remap_paste", (ord("p"),)),
        pending=_remap_tuple(state, "remap_pending", pending),
        bar_next=bar_next,
        bar_prev=bar_prev,
        page_up=_remap_tuple(state, "remap_page_up", page_up),
        page_down=_remap_tuple(state, "remap_page_down", page_down),
        scroll_up=_remap_tuple(state, "remap_scroll_up", scroll_up),
        scroll_down=_remap_tuple(state, "remap_scroll_down", scroll_down),
        section_prev=_remap_tuple(state, "remap_section_prev", (ord("["),)) if state.read_only else (),
        section_next=_remap_tuple(state, "remap_section_next", (ord("]"),)) if state.read_only else (),
        col_start=col_start,
        col_end=col_end,
        jump_bottom=_remap_tuple(state, "remap_jump_bottom", (ord("G"),)),
        find_forward=_remap_tuple(state, "remap_find_forward", (ord("f"),)),
        find_backward=_remap_tuple(state, "remap_find_backward", (ord("F"),)),
        till_forward=_remap_tuple(state, "remap_till_forward", (ord("t"),)),
        till_backward=_remap_tuple(state, "remap_till_backward", (ord("T"),)),
        find_repeat=_remap_tuple(state, "remap_find_repeat", find_repeat),
        find_repeat_reverse=_remap_tuple(state, "remap_find_repeat_reverse", find_repeat_reverse),
        word_search_forward=_remap_tuple(state, "remap_word_search_forward", (ord("*"),)),
        word_search_backward=_remap_tuple(state, "remap_word_search_backward", (ord("#"),)),
        word_search_next=_remap_tuple(state, "remap_word_search_next", (ord("n"),)),
        word_search_prev=_remap_tuple(state, "remap_word_search_prev", (ord("N"),)),
        match_jump=_remap_tuple(state, "remap_match_jump", (ord("%"),)),
        mark_set=_remap_tuple(state, "remap_mark_set", (ord("m"),)),
        mark_jump_line=_remap_tuple(state, "remap_mark_jump_line", (ord("'"),)),
        mark_jump_exact=_remap_tuple(state, "remap_mark_jump_exact", (ord("`"),)),
    )


def pending_bindings() -> PendingBindings:
    return PendingBindings(
        gg=(ord("g"),),
        gh=(ord("h"),),
        gj=(ord("j"),),
        gi=(ord("i"),),
        gp=(ord("p"),),
        gr=(ord("r"),),
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
        download_tree=(ord("D"),),
        search=(ord("/"),),
        prefix=(ord("g"),),
        bottom=(ord("G"),),
        enter=(keycodes.enter, 10, 13),
        backspace=(keycodes.backspace, 127, 8),
        escape=(27, keycodes.exit),
    )
