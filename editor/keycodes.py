from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyCodes:
    left: int
    right: int
    up: int
    down: int
    f1: int
    ic: int
    dc: int
    enter: int
    exit: int
    backspace: int
    ppage: int
    npage: int
    home: int
    end: int
    tab: int


DEFAULT_KEYCODES = KeyCodes(
    left=260,
    right=261,
    up=259,
    down=258,
    f1=265,
    ic=331,
    dc=330,
    enter=343,
    exit=361,
    backspace=263,
    ppage=339,
    npage=338,
    home=262,
    end=360,
    tab=9,
)
