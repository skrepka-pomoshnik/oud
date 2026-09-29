from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from queue import SimpleQueue
from threading import Thread
from typing import TYPE_CHECKING, NotRequired, TypedDict

from oud.editor.core.coordinates import clamp_cursor, stop_at_column, stop_column
from oud.editor.core.document import DocumentMode
from oud.editor.core.feedback.messages import MessageLevel, infer_message_level
from oud.editor.core.feedback.transient import DEFAULT_MESSAGE_TTL_TICKS
from oud.editor.core.input.keycodes import DEFAULT_KEYCODES, KeyCodes
from oud.editor.core.input.modes import Mode
from oud.services.playback.timeline import PlaybackCursor
from petrucci.core.model import Bar, Chord, ImportedBarContent, Piece

if TYPE_CHECKING:
    from oud.editor.core.input.keymap import Action
    from oud.importers.tab import TabData
    from oud.services.plugins.model import RemoteTab
    from petrucci.terminal.canvas.framebuffer import Frame


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
        # The cursor rests on an event onset or the append slot, in whole notes.
        self.cursor_onset = Fraction(0)
        self.bar_offset = 0
        self.bar_width = 12
        self.mode: Mode = Mode.NORMAL
        self.overrides: dict[tuple[int, int, int], str] = {}
        self.durations: dict[tuple[int, int, int], int] = {}
        self.current_duration = 4
        self.cmdline = ""
        self.searchline = ""
        self._message = ""
        self._message_level = MessageLevel.INFO
        self.message_ttl_ticks = 0
        self.message = ""
        self.path: str | None = None
        self.write_path: str | None = None
        self.suggested_write_path: str | None = None
        self.source_format = "new"
        self.document_mode = DocumentMode.NATIVE
        self.forced_read_only = False
        self.persistent_notice = ""
        self.persistent_notice_level = MessageLevel.INFO
        self.pending_overwrite_path: str | None = None
        self.view_staff_index = 0
        self.modified = False
        self.clean_undo_depth = 0
        self.undo_stack: list[UndoAction] = []
        self.redo_stack: list[UndoAction] = []
        self.undo_group_stack: list[UndoGroupFrame] = []
        self.history = PromptHistoryState()
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
        self.glisses: list[tuple[int, int, int]] = []
        self._slur_start: tuple[int, int] | None = None
        self._tie_start: tuple[int, int] | None = None
        self._hold_start: tuple[int, int] | None = None
        self.help_offset = 0
        self.info_offset = 0
        self.notes_offset = 0
        self.screen_width = 0
        self.screen_height = 0
        # Per-bar logical-col -> display-col maps published by the renderer each
        # frame; motion uses them so the cursor moves exactly as drawn.
        self.display_cursor_maps: dict[int, list[int]] = {}
        self.system_layout_cache_key: tuple[object, ...] | None = None
        self.system_layout_cache_starts: tuple[int, ...] = ()
        self.midi_proc: subprocess.Popen[bytes] | None = None
        self.pdf_job: Thread | None = None
        self.background_messages: SimpleQueue[tuple[str, str]] = SimpleQueue()
        self.playback = PlaybackState()
        self.count_prefix = ""
        # Keys of an unfinished sequence (`g`, `d`) and an action awaiting its char (`f{c}`).
        self.pending_keys: tuple[int, ...] = ()
        self.pending_action: Action | None = None
        self.last_find: tuple[str, str] | None = None
        self.last_word_search: tuple[str, int] | None = None
        self.marks: dict[str, tuple[int, int, int]] = {}
        self.pending_quit = False
        self.read_only = False
        self.visual_anchor: tuple[int, int, int] | None = None
        self.yanked_rows: list[tuple[int, int, str]] | None = None
        self.yanked_bar: YankedBar | None = None
        self.yanked_bars: list[YankedBar] | None = None
        self.yanked_chords: list[Chord] | None = None
        self.stave_breaks: set[int] = set()
        self.config_path = config_path
        self.keycodes = keycodes or DEFAULT_KEYCODES
        self.plugins = PluginViewState()
        self.suspend_tui: Callable[[], None] | None = None
        self.resume_tui: Callable[[], None] | None = None
        self.dirty_rows: set[int] = set()
        self.last_frame: Frame | None = None
        self.last_base_frame: Frame | None = None
        self.last_frame_size: tuple[int, int] | None = None
        self.playback_overlay_cache: dict[tuple[int, int], list[tuple[int, int, str, int]]] | None = None
        self.playback_overlay_key: tuple[int, int] | None = None
        self.tab_data: TabData | None = None
        self.viewport_scroll_hold_ticks = 0

    def clamp(self) -> None:
        clamp_cursor(self)

    @property
    def cursor_col(self) -> int:
        """Display-grid column drawn for the cursor stop."""

        return stop_column(self, self.cursor_bar, self.cursor_onset)

    @cursor_col.setter
    def cursor_col(self, column: int) -> None:
        """Move to the stop drawn at or before ``column`` in the cursor bar."""

        self.cursor_onset = stop_at_column(self, self.cursor_bar, column)

    @property
    def message(self) -> str:
        return self._message

    @message.setter
    def message(self, value: str) -> None:
        self._message = value
        self._message_level = infer_message_level(value)
        self.message_ttl_ticks = DEFAULT_MESSAGE_TTL_TICKS if value else 0

    @property
    def message_level(self) -> MessageLevel:
        return self._message_level

    def notify(self, value: str, level: MessageLevel) -> None:
        self.message = value
        self._message_level = level

    @property
    def visible_message(self) -> str:
        return self.message or self.persistent_notice

    @property
    def visible_message_level(self) -> MessageLevel:
        return self.message_level if self.message else self.persistent_notice_level

    @property
    def command_history(self) -> list[str]:
        return self.history.command

    @command_history.setter
    def command_history(self, value: list[str]) -> None:
        self.history.command = value

    @property
    def command_history_index(self) -> int | None:
        return self.history.command_index

    @command_history_index.setter
    def command_history_index(self, value: int | None) -> None:
        self.history.command_index = value

    @property
    def search_history(self) -> list[str]:
        return self.history.search

    @search_history.setter
    def search_history(self, value: list[str]) -> None:
        self.history.search = value

    @property
    def search_history_index(self) -> int | None:
        return self.history.search_index

    @search_history_index.setter
    def search_history_index(self, value: int | None) -> None:
        self.history.search_index = value

    @property
    def playback_timeline(self) -> list[PlaybackCursor]:
        return self.playback.timeline

    @playback_timeline.setter
    def playback_timeline(self, value: list[PlaybackCursor]) -> None:
        self.playback.timeline = value

    @property
    def playback_started_at(self) -> float | None:
        return self.playback.started_at

    @playback_started_at.setter
    def playback_started_at(self, value: float | None) -> None:
        self.playback.started_at = value

    @property
    def playback_index(self) -> int:
        return self.playback.index

    @playback_index.setter
    def playback_index(self, value: int) -> None:
        self.playback.index = value

    @property
    def playback_bar(self) -> int | None:
        return self.playback.bar

    @playback_bar.setter
    def playback_bar(self, value: int | None) -> None:
        self.playback.bar = value

    @property
    def playback_col(self) -> int | None:
        return self.playback.col

    @playback_col.setter
    def playback_col(self, value: int | None) -> None:
        self.playback.col = value

    @property
    def plugin_items(self) -> list[RemoteTab]:
        return self.plugins.items

    @plugin_items.setter
    def plugin_items(self, value: list[RemoteTab]) -> None:
        self.plugins.items = value

    @property
    def plugin_index(self) -> int:
        return self.plugins.index

    @plugin_index.setter
    def plugin_index(self, value: int) -> None:
        self.plugins.index = value

    @property
    def plugin_offset(self) -> int:
        return self.plugins.offset

    @plugin_offset.setter
    def plugin_offset(self, value: int) -> None:
        self.plugins.offset = value

    @property
    def plugin_title(self) -> str:
        return self.plugins.title

    @plugin_title.setter
    def plugin_title(self, value: str) -> None:
        self.plugins.title = value

    @property
    def plugin_stack(self) -> list[tuple[str, list[RemoteTab], int, int, str | None]]:
        return self.plugins.stack

    @plugin_stack.setter
    def plugin_stack(self, value: list[tuple[str, list[RemoteTab], int, int, str | None]]) -> None:
        self.plugins.stack = value

    @property
    def plugin_name(self) -> str | None:
        return self.plugins.name

    @plugin_name.setter
    def plugin_name(self, value: str | None) -> None:
        self.plugins.name = value

    @property
    def plugin_query(self) -> str:
        return self.plugins.query

    @plugin_query.setter
    def plugin_query(self, value: str) -> None:
        self.plugins.query = value

    @property
    def plugin_query_active(self) -> bool:
        return self.plugins.query_active

    @plugin_query_active.setter
    def plugin_query_active(self, value: bool) -> None:
        self.plugins.query_active = value

    @property
    def plugin_pending(self) -> str:
        return self.plugins.pending

    @plugin_pending.setter
    def plugin_pending(self, value: str) -> None:
        self.plugins.pending = value


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
    glisses: list[tuple[int, int, int]]
    marks: dict[str, tuple[int, int, int]]


@dataclass
class UndoAction:
    kind: str
    data: dict[str, object]


@dataclass
class UndoGroupFrame:
    label: str | None = None
    cursor_before: tuple[int, int, Fraction] | None = None
    actions: list[UndoAction] = field(default_factory=list)


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
    glisses: list[tuple[int, int, int]]
    marks: dict[str, tuple[int, int, int]]
    # Notation-staff content of the bar (staff index, content), for scores with other staffs.
    imported: NotRequired[list[tuple[int, ImportedBarContent]]]


@dataclass
class PromptHistoryState:
    command: list[str] = field(default_factory=list)
    command_index: int | None = None
    search: list[str] = field(default_factory=list)
    search_index: int | None = None


@dataclass
class PlaybackState:
    timeline: list[PlaybackCursor] = field(default_factory=list)
    started_at: float | None = None
    index: int = 0
    bar: int | None = None
    col: int | None = None
    markers: list[tuple[int, int]] = field(default_factory=list)
    verse: int | None = None


@dataclass
class PluginViewState:
    items: list[RemoteTab] = field(default_factory=list)
    index: int = 0
    offset: int = 0
    title: str = "Plugins"
    stack: list[tuple[str, list[RemoteTab], int, int, str | None]] = field(default_factory=list)
    name: str | None = None
    query: str = ""
    query_active: bool = False
    pending: str = ""
    confirm: str = ""
