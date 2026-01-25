from __future__ import annotations

import curses

from editor.keycodes import KeyCodes


def keycodes_from_curses() -> KeyCodes:
    return KeyCodes(
        left=curses.KEY_LEFT,
        right=curses.KEY_RIGHT,
        up=curses.KEY_UP,
        down=curses.KEY_DOWN,
        f1=getattr(curses, "KEY_F1", 265),
        ic=getattr(curses, "KEY_IC", 331),
        dc=getattr(curses, "KEY_DC", 330),
        enter=getattr(curses, "KEY_ENTER", 10),
        exit=getattr(curses, "KEY_EXIT", 27),
        backspace=getattr(curses, "KEY_BACKSPACE", 127),
        ppage=getattr(curses, "KEY_PPAGE", 339),
        npage=getattr(curses, "KEY_NPAGE", 338),
        home=getattr(curses, "KEY_HOME", 262),
        end=getattr(curses, "KEY_END", 360),
        tab=getattr(curses, "KEY_TAB", 9),
    )
