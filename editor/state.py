from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TypedDict

from core.model import Bar, Piece


class EditorState:
    def __init__(self, piece: Piece, settings: dict[str, str]) -> None:
        self.piece = piece
        self.cursor_bar = 0
        self.cursor_string = 0
        self.cursor_col = 0
        self.bar_offset = 0
        self.bar_width = 12
        self.mode = "normal"
        self.overrides: dict[tuple[int, int, int], str] = {}
        self.durations: dict[tuple[int, int, int], int] = {}
        self.current_duration = 4
        self.cmdline = ""
        self.searchline = ""
        self.message = ""
        self.path: str | None = None
        self.modified = False
        self.undo_stack: list[UndoAction] = []
        self.redo_stack: list[UndoAction] = []
        self.command_history: list[str] = []
        self.command_history_index: int | None = None
        self.settings = settings
        self.replace_once = False
        self.insert_prefix = ""
        self.ascii_preview = False
        self.ornaments: dict[tuple[int, int], str] = {}
        self.annotations: dict[tuple[int, int], str] = {}
        self.highlights: set[tuple[int, int, int]] = set()
        self.dotted: set[tuple[int, int]] = set()
        self.slurs: list[tuple[int, int, int]] = []
        self.ties: list[tuple[int, int, int]] = []
        self.holds: list[tuple[int, int, int]] = []
        self._slur_start: tuple[int, int] | None = None
        self._tie_start: tuple[int, int] | None = None
        self._hold_start: tuple[int, int] | None = None
        self.help_offset = 0
        self.info_offset = 0
        self.screen_width = 0
        self.screen_height = 0
        self.midi_proc: subprocess.Popen[bytes] | None = None
        self.count_prefix = ""
        self.pending_key = ""
        self.yanked_bar: YankedBar | None = None
        self.stave_breaks: set[int] = set()

    def clamp(self) -> None:
        bar_count = max(1, len(self.piece.bars))
        self.cursor_bar = max(0, min(self.cursor_bar, bar_count - 1))
        self.cursor_string = max(0, min(self.cursor_string, self.piece.strings - 1))
        self.cursor_col = max(0, min(self.cursor_col, self.bar_width - 1))


@dataclass
class YankedBar:
    bar: Bar
    overrides: dict[tuple[int, int, int], str]
    durations: dict[tuple[int, int, int], int]
    annotations: dict[tuple[int, int], str]
    ornaments: dict[tuple[int, int], str]
    dotted: set[tuple[int, int]]
    slurs: list[tuple[int, int, int]]
    ties: list[tuple[int, int, int]]
    holds: list[tuple[int, int, int]]


@dataclass
class UndoAction:
    kind: str
    data: dict[str, object]


class BarSnapshot(TypedDict):
    bar: Bar
    overrides: dict[tuple[int, int, int], str]
    durations: dict[tuple[int, int, int], int]
    annotations: dict[tuple[int, int], str]
    ornaments: dict[tuple[int, int], str]
    highlights: set[tuple[int, int, int]]
    dotted: set[tuple[int, int]]
    slurs: list[tuple[int, int, int]]
    ties: list[tuple[int, int, int]]
    holds: list[tuple[int, int, int]]
