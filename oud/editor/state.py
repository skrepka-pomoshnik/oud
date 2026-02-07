from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from oud.core.model import Bar, Piece
from oud.editor.controller_utils import clamp_cursor
from oud.editor.keycodes import DEFAULT_KEYCODES, KeyCodes

if TYPE_CHECKING:
    from oud.core.plugin_model import RemoteTab
    from oud.ui.framebuffer import Frame


class EditorState:
    def __init__(
        self,
        piece: Piece,
        settings: dict[str, str],
        *,
        config_path: str = "config.toml",
        keycodes: KeyCodes | None = None,
    ) -> None:
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
        self.search_history: list[str] = []
        self.search_history_index: int | None = None
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
        self.playback_timeline: list[tuple[float, float, int, int]] = []
        self.playback_started_at: float | None = None
        self.playback_index = 0
        self.playback_bar: int | None = None
        self.playback_col: int | None = None
        self.count_prefix = ""
        self.pending_key = ""
        self.pending_find = ""
        self.last_find: tuple[str, str] | None = None
        self.last_word_search: tuple[str, int] | None = None
        self.marks: dict[str, tuple[int, int, int]] = {}
        self.pending_mark = ""
        self.pending_quit = False
        self.yanked_bar: YankedBar | None = None
        self.stave_breaks: set[int] = set()
        self.config_path = config_path
        self.keycodes = keycodes or DEFAULT_KEYCODES
        self.plugin_items: list[RemoteTab] = []
        self.plugin_index = 0
        self.plugin_offset = 0
        self.plugin_title = "Plugins"
        self.plugin_stack: list[tuple[str, list[RemoteTab], int, int, str | None]] = []
        self.plugin_name: str | None = None
        self.plugin_query = ""
        self.plugin_query_active = False
        self.plugin_pending = ""
        self.suspend_tui: Callable[[], None] | None = None
        self.resume_tui: Callable[[], None] | None = None
        self.dirty_rows: set[int] = set()
        self.last_frame: Frame | None = None
        self.last_frame_size: tuple[int, int] | None = None

    def clamp(self) -> None:
        clamp_cursor(self)


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
