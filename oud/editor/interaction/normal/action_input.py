from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionInput:
    key: int
    char: str = ""
