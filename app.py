from __future__ import annotations

import curses
import os
import sys
from pathlib import Path

from export_tab import export_ascii, export_tab_to_file
from ft3 import build_durations, load_ft3
from lilypond import export_lilypond, print_lilypond_pdf
from midi import export_midi, play_midi
from model import Bar, Piece
from render import _block_height, render_piece
from settings import DEFAULT_SETTINGS, load_settings, save_settings
from tab_parser import load_tab

DEFAULT_BAR_WIDTH = 12
CONFIG_PATH = "config.toml"


class EditorState:
    def __init__(self, piece: Piece, settings: dict[str, str]) -> None:
        self.piece = piece
        self.cursor_bar = 0
        self.cursor_string = 0
        self.cursor_col = 0
        self.bar_offset = 0
        self.bar_width = DEFAULT_BAR_WIDTH
        self.mode = "normal"
        self.overrides: dict[tuple[int, int, int], str] = {}
        self.durations: dict[tuple[int, int, int], int] = {}
        self.cmdline = ""
        self.searchline = ""
        self.message = ""
        self.path: str | None = None
        self.modified = False
        self.undo_stack: list[tuple[str, tuple[int, int, int], object | None, object | None]] = []
        self.command_history: list[str] = []
        self.command_history_index: int | None = None
        self.settings = settings
        self.replace_once = False
        self.ascii_preview = False
        self.ornaments: dict[tuple[int, int], str] = {}
        self.annotations: dict[tuple[int, int], str] = {}
        self.highlights: set[tuple[int, int, int]] = set()
        self.slurs: list[tuple[int, int, int]] = []
        self.ties: list[tuple[int, int, int]] = []
        self.holds: list[tuple[int, int, int]] = []
        self._slur_start: tuple[int, int] | None = None
        self._tie_start: tuple[int, int] | None = None
        self._hold_start: tuple[int, int] | None = None
        self.help_offset = 0
        self.screen_width = 0
        self.screen_height = 0

    def clamp(self) -> None:
        bar_count = max(1, len(self.piece.bars))
        self.cursor_bar = max(0, min(self.cursor_bar, bar_count - 1))
        self.cursor_string = max(0, min(self.cursor_string, self.piece.strings - 1))
        self.cursor_col = max(0, min(self.cursor_col, self.bar_width - 1))


def _bars_per_line(state: EditorState, width: int) -> int:
    left_margin = 3
    bar_gap = 2
    usable_width = max(0, width - left_margin)
    return max(1, usable_width // (state.bar_width + bar_gap))


def _rows_per_screen(state: EditorState, height: int) -> int:
    include_meta = True
    show_dur = state.settings.get("showdur", "off") == "on"
    show_extras = state.settings.get("showextras", "off") == "on"
    show_tactus = state.settings.get("showtactus", "off") == "on"
    block_h = _block_height(include_meta, state.piece.strings, show_dur, show_extras, show_tactus)
    available = max(0, height - 2 - 1)
    return max(1, available // block_h)


def _ensure_cursor_visible(state: EditorState, width: int, height: int) -> None:
    bars_per_line = _bars_per_line(state, width)
    rows_per_screen = _rows_per_screen(state, height)
    cursor_row = state.cursor_bar // bars_per_line
    first_row = state.bar_offset // bars_per_line
    if cursor_row < first_row:
        state.bar_offset = cursor_row * bars_per_line
    if cursor_row >= first_row + rows_per_screen:
        state.bar_offset = (cursor_row - rows_per_screen + 1) * bars_per_line

def _allow_arrows(state: EditorState) -> bool:
    return state.settings.get("keys", "vim+arrows") != "vim"


def _string_index(state: EditorState, display_index: int) -> int:
    if (
        state.settings.get("style") == "italian"
        and state.settings.get("italianorient") == "reverse"
    ):
        return state.piece.strings - 1 - display_index
    return display_index


def _cursor_key(state: EditorState) -> tuple[int, int, int]:
    return (state.cursor_bar, _string_index(state, state.cursor_string), state.cursor_col)


def _move_left(state: EditorState) -> None:
    if state.cursor_col > 0:
        state.cursor_col -= 1
    elif state.cursor_bar > 0:
        state.cursor_bar -= 1
        state.cursor_col = state.bar_width - 1


def _move_right(state: EditorState) -> None:
    if state.cursor_col < state.bar_width - 1:
        state.cursor_col += 1
    elif state.cursor_bar < len(state.piece.bars) - 1:
        state.cursor_bar += 1
        state.cursor_col = 0
    else:
        state.piece.bars.append(Bar())
        state.cursor_bar += 1
        state.cursor_col = 0
        state.modified = True


def _duration_value(key: int, style: str) -> int | None:
    french_map = {
        ord("1"): 1,
        ord("2"): 2,
        ord("3"): 4,
        ord("4"): 8,
        ord("5"): 16,
        ord("6"): 32,
        ord("7"): 64,
    }
    letter_map = {
        ord("w"): 1,
        ord("h"): 2,
        ord("q"): 4,
        ord("e"): 8,
        ord("s"): 16,
        ord("t"): 32,
        ord("W"): 1,
        ord("H"): 2,
        ord("Q"): 4,
        ord("E"): 8,
        ord("S"): 16,
        ord("T"): 32,
    }
    if style == "italian":
        return letter_map.get(key)
    return french_map.get(key) or letter_map.get(key)

def _is_french_fret(ch: str) -> bool:
    return "a" <= ch <= "p"

def _is_italian_fret(ch: str) -> bool:
    return ch.isdigit() or ch == "x"

def _tuning_preset(value: str) -> str | None:
    presets = {
        "renaissance": "C4D4E4F4G4c3f3a2d2g2",
        "guitar": "e4a3d3f+3b2e2",
        "dminor": "a4b-4c4d4e4f4g4a3d3f3a2d2f2",
        "sharp": "c4d4e4f+4g4a3d3g3b2d2f+2",
        "flat": "c4d4e-4f4g4a3d3g3a+2d2f2",
    }
    return presets.get(value)

def _french_to_fret(ch: str) -> int | None:
    if "a" <= ch <= "p":
        return ord(ch) - ord("a")
    return None


def _fret_to_french(fret: int) -> str | None:
    if 0 <= fret <= 15:
        return chr(ord("a") + fret)
    return None


def _italian_to_fret(ch: str) -> int | None:
    if ch.isdigit():
        return int(ch)
    if ch == "x":
        return 10
    return None


def _fret_to_italian(fret: int) -> str | None:
    if 0 <= fret <= 9:
        return str(fret)
    if fret == 10:
        return "x"
    return None


def _convert_overrides(state: EditorState, target_style: str) -> None:
    converted = 0
    skipped = 0
    items = list(state.overrides.items())
    for key, ch in items:
        if target_style == "italian":
            fret = _french_to_fret(ch)
            out = _fret_to_italian(fret) if fret is not None else None
        else:
            fret = _italian_to_fret(ch)
            out = _fret_to_french(fret) if fret is not None else None
        if out is None:
            skipped += 1
            continue
        _apply_override(state, key, out)
        converted += 1
    state.message = f"Converted {converted}, skipped {skipped}"

def _record_undo(
    state: EditorState,
    kind: str,
    key: tuple[int, int, int],
    prev: object | None,
    new: object | None,
) -> None:
    state.undo_stack.append((kind, key, prev, new))
    state.modified = True


def _apply_override(state: EditorState, key: tuple[int, int, int], ch: str) -> None:
    prev = state.overrides.get(key)
    state.overrides[key] = ch
    _record_undo(state, "override", key, prev, ch)


def _apply_duration(state: EditorState, key: tuple[int, int, int], dur: int) -> None:
    prev = state.durations.get(key)
    state.durations[key] = dur
    _record_undo(state, "duration", key, prev, dur)


def _undo(state: EditorState) -> None:
    if not state.undo_stack:
        state.message = "Nothing to undo"
        return
    kind, key, prev, _new = state.undo_stack.pop()
    if kind == "override":
        if prev is None:
            state.overrides.pop(key, None)
        else:
            state.overrides[key] = prev  # type: ignore[assignment]
    elif kind == "duration":
        if prev is None:
            state.durations.pop(key, None)
        else:
            state.durations[key] = prev  # type: ignore[assignment]
    state.modified = True
    state.message = "Undone"

def _handle_insert(state: EditorState, key: int) -> bool:
    if key in (27, curses.KEY_EXIT):  # ESC
        state.mode = "normal"
        state.replace_once = False
        return True
    if key in (ord("q"), ord("Q")):
        return False
    if key in (ord("h"),) or (key == curses.KEY_LEFT and _allow_arrows(state)):
        _move_left(state)
        return True
    if key in (ord("l"),) or (key == curses.KEY_RIGHT and _allow_arrows(state)):
        _move_right(state)
        return True
    if key in (ord("k"),) or (key == curses.KEY_UP and _allow_arrows(state)):
        state.cursor_string -= 1
        return True
    if key in (ord("j"),) or (key == curses.KEY_DOWN and _allow_arrows(state)):
        state.cursor_string += 1
        return True

    style = state.settings.get("style", "french")
    dur = _duration_value(key, style)
    if dur is not None:
        cell = _cursor_key(state)
        _apply_duration(state, cell, dur)
        return True

    if 32 <= key <= 126:
        ch = chr(key).lower()
        valid = _is_french_fret(ch) if style == "french" else _is_italian_fret(ch)
        if valid:
            cell = _cursor_key(state)
            _apply_override(state, cell, ch)
            if state.replace_once:
                state.replace_once = False
                state.mode = "normal"
            else:
                steps = 2 if state.settings.get("grid") == "on" else 1
                for _ in range(steps):
                    _move_right(state)
        else:
            state.message = "Invalid fret for current style"
    return True


def _status_line(state: EditorState) -> str:
    name = state.path.split("/")[-1] if state.path else "[No file]"
    mod = "*" if state.modified else ""
    bar = state.cursor_bar + 1
    string = state.cursor_string + 1
    col = state.cursor_col + 1
    style = state.settings.get("style", "french")
    flagstyle = state.settings.get("flagstyle", "standard")
    return f"{name}{mod}  bar:{bar} str:{string} col:{col}  style:{style} flag:{flagstyle}"


def _cmd_open(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path:
        state.message = "No path"
        return
    state.piece = load_tab(path) if path.lower().endswith(".tab") else load_ft3(path)
    state.path = path
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_col = 0
    state.bar_offset = 0
    state.mode = "normal"
    state.message = f"Opened {path}"


def _cmd_set(state: EditorState, args: str) -> None:
    _apply_set_command(state, args.strip())


def _cmd_convert(state: EditorState, args: str) -> None:
    target = args.strip()
    if target not in ("french", "italian"):
        state.message = "Convert target must be french or italian"
        return
    _convert_overrides(state, target)
    state.settings["style"] = target
    save_settings(CONFIG_PATH, state.settings)


def _cmd_ascii(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("on", "off"):
        state.message = "Ascii must be on/off"
        return
    state.ascii_preview = value == "on"
    state.message = f"Ascii preview {value}"


def _cmd_midi(state: EditorState, args: str) -> None:
    path = args.strip() or "out.mid"
    try:
        bpm = int(state.settings.get("tempo", "90") or "90")
    except ValueError:
        bpm = 90
    state.message = export_midi(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        bpm=bpm,
    )


def _cmd_lilypond(state: EditorState, args: str) -> None:
    path = args.strip() or "out.ly"
    state.message = export_lilypond(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )


def _cmd_play(state: EditorState, args: str) -> None:
    target = args.strip()
    start_bar = None
    if target.isdigit():
        start_bar = max(0, int(target) - 1)
        path = _midi_output_path(state)
    else:
        path = target or _midi_output_path(state)
    _play_midi(state, start_bar=start_bar, path=path)


def _cmd_orn(state: EditorState, args: str) -> None:
    _set_ornament(state, args.strip())


def _cmd_annot(state: EditorState, args: str) -> None:
    _set_annotation(state, args.strip())


def _cmd_highlight(state: EditorState, args: str) -> None:
    _set_highlight(state, args.strip())


def _cmd_slur(state: EditorState, args: str) -> None:
    _set_slur(state, args.strip())


def _cmd_tie(state: EditorState, args: str) -> None:
    _set_tie(state, args.strip())


def _cmd_hold(state: EditorState, args: str) -> None:
    _set_hold(state, args.strip())


def _cmd_barline(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("thin", "thick", "double", "hidden", "pale"):
        state.message = "Barline must be thin/thick/double/hidden/pale"
        return
    _set_barline(state, value)


def _cmd_repeat(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("none", "start", "end", "dots"):
        state.message = "Repeat must be none/start/end/dots"
        return
    _set_repeat(state, value)


def _cmd_write(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path and state.path:
        path = state.path if state.path.endswith(".tab") else state.path + ".tab"
    if not path:
        state.message = "No path for write"
        return
    export_tab_to_file(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )
    state.modified = False
    state.message = f"Wrote {path}"


def _cmd_write_ascii(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path and state.path:
        path = state.path if state.path.endswith(".txt") else state.path + ".txt"
    if not path:
        state.message = "No path for wa"
        return
    content = export_ascii(
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    state.modified = False
    state.message = f"Wrote {path}"


def _apply_command(state: EditorState, cmdline: str) -> None:
    cmdline = cmdline.strip()
    if not cmdline:
        return
    if cmdline in ("q", "quit"):
        raise SystemExit(0)
    cmd, *rest = cmdline.split(maxsplit=1)
    args = rest[0] if rest else ""
    handlers = {
        "e": _cmd_open,
        "set": _cmd_set,
        "convert": _cmd_convert,
        "ascii": _cmd_ascii,
        "midi": _cmd_midi,
        "lilypond": _cmd_lilypond,
        "play": _cmd_play,
        "orn": _cmd_orn,
        "annot": _cmd_annot,
        "highlight": _cmd_highlight,
        "slur": _cmd_slur,
        "tie": _cmd_tie,
        "hold": _cmd_hold,
        "barline": _cmd_barline,
        "repeat": _cmd_repeat,
        "w": _cmd_write,
        "wa": _cmd_write_ascii,
    }
    handler = handlers.get(cmd)
    if handler is None:
        state.message = f"Unknown command: {cmdline}"
        return
    handler(state, args)


def _apply_set_command(state: EditorState, args: str) -> None:
    if not args:
        state.message = "No set args"
        return
    for token in args.split():
        if "=" not in token:
            state.message = f"Invalid set token: {token}"
            continue
        key, value = token.split("=", 1)
        if key in ("strings", "staff"):
            try:
                count = int(value)
            except ValueError:
                state.message = f"Invalid {key} value"
                continue
            if count < 4 or count > 7:
                state.message = "Strings must be 4-7"
                continue
            state.piece.strings = count
            state.cursor_string = min(state.cursor_string, count - 1)
            state.settings["strings"] = str(count)
        elif key == "style":
            if value not in ("french", "italian"):
                state.message = "Style must be french or italian"
                continue
            state.settings["style"] = value
        elif key == "measures":
            if value not in ("start", "every", "five"):
                state.message = "Measures must be start/every/five"
                continue
            state.settings["measures"] = value
        elif key == "tuning":
            preset = _tuning_preset(value)
            state.settings["tuning"] = preset if preset else value
        elif key == "flagstyle":
            allowed = {"standard", "italian", "thin", "board", "capirola"}
            if value not in allowed:
                state.message = "Flagstyle must be standard/italian/thin/board/capirola"
                continue
            state.settings["flagstyle"] = value
        elif key in ("time", "timesig"):
            state.settings["time"] = value
        elif key == "key":
            state.settings["key"] = value
        elif key == "countdots":
            if value not in ("on", "off"):
                state.message = "Countdots must be on/off"
                continue
            state.settings["countdots"] = value
        elif key == "keys":
            if value not in ("vim", "vim+arrows"):
                state.message = "Keys must be vim or vim+arrows"
                continue
            state.settings["keys"] = value
        elif key == "spacing":
            try:
                spacing = int(value)
            except ValueError:
                state.message = "Spacing must be int"
                continue
            state.bar_width = max(4, spacing)
            state.settings["spacing"] = str(spacing)
        elif key == "linelen":
            if not value.isdigit():
                state.message = "Linelen must be int"
                continue
            state.settings["linelen"] = value
        elif key == "staffthick":
            if not value.isdigit():
                state.message = "Staffthick must be int"
                continue
            state.settings["staffthick"] = value
        elif key == "fontstyle":
            if value not in ("modern", "renaissance", "baroque"):
                state.message = "Fontstyle must be modern/renaissance/baroque"
                continue
            state.settings["fontstyle"] = value
        elif key == "charstyle":
            state.settings["charstyle"] = value
        elif key == "midipatch":
            if not value.isdigit():
                state.message = "Midipatch must be int"
                continue
            state.settings["midipatch"] = value
        elif key == "tempo":
            if not value.isdigit():
                state.message = "Tempo must be int"
                continue
            state.settings["tempo"] = value
        elif key == "grid":
            if value not in ("on", "off"):
                state.message = "Grid must be on/off"
                continue
            state.settings["grid"] = value
        elif key == "showdur":
            if value not in ("on", "off"):
                state.message = "Showdur must be on/off"
                continue
            state.settings["showdur"] = value
        elif key == "showextras":
            if value not in ("on", "off"):
                state.message = "Showextras must be on/off"
                continue
            state.settings["showextras"] = value
        elif key == "showtactus":
            if value not in ("on", "off"):
                state.message = "Showtactus must be on/off"
                continue
            state.settings["showtactus"] = value
        elif key == "italianorient":
            if value not in ("normal", "reverse"):
                state.message = "Italianorient must be normal/reverse"
                continue
            state.settings["italianorient"] = value
        elif key == "frenchc":
            if value not in ("normal", "alt"):
                state.message = "Frenchc must be normal/alt"
                continue
            state.settings["frenchc"] = value
        elif key == "frenche":
            if value not in ("normal", "tail"):
                state.message = "Frenche must be normal/tail"
                continue
            state.settings["frenche"] = value
        else:
            state.message = f"Unknown set key: {key}"
    save_settings(CONFIG_PATH, state.settings)


def _set_ornament(state: EditorState, value: str) -> None:
    key = (state.cursor_bar, state.cursor_col)
    if value == "clear":
        state.ornaments.pop(key, None)
        state.message = "Ornament cleared"
        return
    if len(value) != 1:
        state.message = "Ornament must be 1 char or clear"
        return
    state.ornaments[key] = value
    state.modified = True
    state.message = f"Ornament {value}"


def _set_annotation(state: EditorState, value: str) -> None:
    key = (state.cursor_bar, state.cursor_col)
    if value == "clear":
        state.annotations.pop(key, None)
        state.message = "Annotation cleared"
        return
    state.annotations[key] = value[:8]
    state.modified = True
    state.message = "Annotation set"


def _set_highlight(state: EditorState, value: str) -> None:
    key = _cursor_key(state)
    if value == "on":
        state.highlights.add(key)
        state.modified = True
        state.message = "Highlight on"
        return
    if value == "off":
        state.highlights.discard(key)
        state.modified = True
        state.message = "Highlight off"
        return
    state.message = "Highlight must be on/off"


def _set_slur(state: EditorState, value: str) -> None:
    pos = (state.cursor_bar, state.cursor_col)
    if value == "start":
        state._slur_start = pos
        state.message = "Slur start"
        return
    if value == "end":
        if state._slur_start and state._slur_start[0] == pos[0]:
            start_col = state._slur_start[1]
            end_col = pos[1]
            if start_col > end_col:
                start_col, end_col = end_col, start_col
            state.slurs.append((pos[0], start_col, end_col))
            state._slur_start = None
            state.modified = True
            state.message = "Slur set"
            return
        state.message = "Slur start not set"
        return
    if value == "clear":
        state.slurs = [s for s in state.slurs if s[0] != state.cursor_bar]
        state.message = "Slur cleared"
        return
    state.message = "Slur must be start/end/clear"


def _set_tie(state: EditorState, value: str) -> None:
    pos = (state.cursor_bar, state.cursor_col)
    if value == "start":
        state._tie_start = pos
        state.message = "Tie start"
        return
    if value == "end":
        if state._tie_start and state._tie_start[0] == pos[0]:
            start_col = state._tie_start[1]
            end_col = pos[1]
            if start_col > end_col:
                start_col, end_col = end_col, start_col
            state.ties.append((pos[0], start_col, end_col))
            state._tie_start = None
            state.modified = True
            state.message = "Tie set"
            return
        state.message = "Tie start not set"
        return
    if value == "clear":
        state.ties = [s for s in state.ties if s[0] != state.cursor_bar]
        state.message = "Tie cleared"
        return
    state.message = "Tie must be start/end/clear"


def _set_hold(state: EditorState, value: str) -> None:
    pos = (state.cursor_bar, state.cursor_col)
    if value == "start":
        state._hold_start = pos
        state.message = "Hold start"
        return
    if value == "end":
        if state._hold_start and state._hold_start[0] == pos[0]:
            start_col = state._hold_start[1]
            end_col = pos[1]
            if start_col > end_col:
                start_col, end_col = end_col, start_col
            state.holds.append((pos[0], start_col, end_col))
            state._hold_start = None
            state.modified = True
            state.message = "Hold set"
            return
        state.message = "Hold start not set"
        return
    if value == "clear":
        state.holds = [s for s in state.holds if s[0] != state.cursor_bar]
        state.message = "Hold cleared"
        return
    state.message = "Hold must be start/end/clear"


def _set_barline(state: EditorState, value: str) -> None:
    if not state.piece.bars:
        state.message = "No bars"
        return
    bar = state.piece.bars[state.cursor_bar]
    mapping = {
        "thin": "|",
        "thick": "||",
        "double": "||",
        "hidden": " ",
        "pale": ":",
    }
    bar.barline = mapping.get(value, "|")
    state.modified = True
    state.message = f"Barline {value}"


def _set_repeat(state: EditorState, value: str) -> None:
    if not state.piece.bars:
        state.message = "No bars"
        return
    bar = state.piece.bars[state.cursor_bar]
    mapping = {
        "none": "",
        "start": ".:",
        "end": ":.",
        "dots": ".",
    }
    bar.repeat = mapping.get(value, "")
    state.modified = True
    state.message = f"Repeat {value}"


def _history_prev(state: EditorState) -> str | None:
    if not state.command_history:
        return None
    if state.command_history_index is None:
        state.command_history_index = len(state.command_history) - 1
    else:
        state.command_history_index = max(0, state.command_history_index - 1)
    return state.command_history[state.command_history_index]


def _history_next(state: EditorState) -> str | None:
    if not state.command_history:
        return None
    if state.command_history_index is None:
        return ""
    state.command_history_index = min(
        len(state.command_history), state.command_history_index + 1
    )
    if state.command_history_index >= len(state.command_history):
        state.command_history_index = None
        return ""
    return state.command_history[state.command_history_index]


def _complete_command(state: EditorState) -> bool:
    cmdline = state.cmdline
    commands = [
        "e",
        "w",
        "wa",
        "ascii",
        "midi",
        "play",
        "lilypond",
        "set",
        "convert",
        "orn",
        "annot",
        "highlight",
        "slur",
        "tie",
        "hold",
        "barline",
        "repeat",
        "q",
        "quit",
    ]
    if " " not in cmdline:
        matches = [cmd for cmd in commands if cmd.startswith(cmdline)]
        if not matches:
            return True
        if len(matches) == 1:
            match = matches[0]
            state.cmdline = match + (" " if match not in ("q", "quit") else "")
            return True
        state.message = "Matches: " + " ".join(matches)
        return True

    cmd, rest = cmdline.split(" ", 1)
    if cmd not in ("e", "w", "wa", "midi", "lilypond"):
        return True
    expanded = os.path.expanduser(rest)
    base_dir = os.path.dirname(expanded) or "."
    base_prefix = os.path.basename(expanded)
    try:
        entries = sorted(os.listdir(base_dir))
    except OSError:
        return True
    matches: list[str] = []
    for entry in entries:
        if not entry.startswith(base_prefix):
            continue
        path = os.path.join(base_dir, entry)
        matches.append(path)
    if not matches:
        return True
    if len(matches) == 1:
        path = matches[0]
        if os.path.isdir(path):
            path = path + os.sep
        state.cmdline = f"{cmd} {path}"
        return True
    common = os.path.commonprefix(matches)
    if common and common != expanded:
        state.cmdline = f"{cmd} {common}"
        return True
    state.message = "Matches: " + " ".join(matches[:8])
    return True


def _handle_command(state: EditorState, key: int) -> bool:
    if key in (27,):  # ESC
        state.mode = "normal"
        state.cmdline = ""
        state.command_history_index = None
        return True
    key_tab = getattr(curses, "KEY_TAB", 9)
    if key in (key_tab, 9):
        return _complete_command(state)
    if key in (curses.KEY_BACKSPACE, 127, 8):
        state.cmdline = state.cmdline[:-1]
        return True
    if key == curses.KEY_UP:
        prev = _history_prev(state)
        if prev is not None:
            state.cmdline = prev
        return True
    if key == curses.KEY_DOWN:
        nxt = _history_next(state)
        if nxt is not None:
            state.cmdline = nxt
        return True
    if key in (curses.KEY_ENTER, 10, 13):
        cmd = state.cmdline
        state.cmdline = ""
        state.mode = "normal"
        state.command_history_index = None
        if cmd:
            state.command_history.append(cmd)
        _apply_command(state, cmd)
        return True
    if 32 <= key <= 126:
        state.cmdline += chr(key)
    return True


def _parse_search(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    if not text.isdigit():
        return None
    value = int(text)
    if value <= 0:
        return None
    return value - 1


def _handle_search(state: EditorState, key: int) -> bool:
    if key in (27,):  # ESC
        state.mode = "normal"
        state.searchline = ""
        return True
    if key in (curses.KEY_BACKSPACE, 127, 8):
        state.searchline = state.searchline[:-1]
        return True
    if key in (curses.KEY_ENTER, 10, 13):
        target = _parse_search(state.searchline)
        state.searchline = ""
        state.mode = "normal"
        if target is None:
            state.message = "Invalid bar"
            return True
        state.cursor_bar = max(0, min(target, len(state.piece.bars) - 1))
        state.cursor_col = 0
        return True
    if 32 <= key <= 126:
        state.searchline += chr(key)
    return True


def _handle_normal(state: EditorState, key: int) -> bool:
    if key in (ord("q"), ord("Q")):
        return False
    if key == ord(":"):
        state.mode = "command"
        state.cmdline = ""
        return True
    if key == ord("?"):
        state.mode = "help"
        state.help_offset = 0
        return True
    if key in (ord("p"), ord("P")):
        _print_pdf(state)
        return True
    if key in (ord("m"), ord("M")):
        _play_midi(state)
        return True
    if key == ord("/"):
        state.mode = "search"
        state.searchline = ""
        return True
    if key in (ord("i"), curses.KEY_ENTER, 10, 13):
        state.mode = "insert"
        return True
    if key == ord("r"):
        state.mode = "insert"
        state.replace_once = True
        return True
    if key == ord("u"):
        _undo(state)
        return True
    if key in (ord("h"),) or (key == curses.KEY_LEFT and _allow_arrows(state)):
        _move_left(state)
    elif key in (ord("l"),) or (key == curses.KEY_RIGHT and _allow_arrows(state)):
        _move_right(state)
    elif key in (ord("k"),) or (key == curses.KEY_UP and _allow_arrows(state)):
        state.cursor_string -= 1
    elif key in (ord("j"),) or (key == curses.KEY_DOWN and _allow_arrows(state)):
        state.cursor_string += 1
    elif key == ord("K"):
        bars_per_line = _bars_per_line(state, state.screen_width)
        state.cursor_bar = max(0, state.cursor_bar - bars_per_line)
        state.cursor_col = 0
    elif key == ord("J"):
        bars_per_line = _bars_per_line(state, state.screen_width)
        state.cursor_bar = min(len(state.piece.bars) - 1, state.cursor_bar + bars_per_line)
        state.cursor_col = 0
    elif key == ord("w"):
        state.cursor_bar = min(len(state.piece.bars) - 1, state.cursor_bar + 1)
        state.cursor_col = 0
    elif key == ord("b"):
        state.cursor_bar = max(0, state.cursor_bar - 1)
        state.cursor_col = 0
    elif key == ord("e"):
        state.cursor_col = state.bar_width - 1
    elif key == ord("{"):
        bars_per_line = _bars_per_line(state, state.screen_width)
        state.cursor_bar = max(0, state.cursor_bar - bars_per_line)
        state.cursor_col = 0
    elif key == ord("}"):
        bars_per_line = _bars_per_line(state, state.screen_width)
        state.cursor_bar = min(len(state.piece.bars) - 1, state.cursor_bar + bars_per_line)
        state.cursor_col = 0
    elif key == ord("g"):
        state.cursor_bar = 0
        state.cursor_col = 0
    elif key == ord("G"):
        state.cursor_bar = max(0, len(state.piece.bars) - 1)
        state.cursor_col = 0
    elif key == ord("0"):
        state.cursor_col = 0
    elif key == ord("$"):
        state.cursor_col = state.bar_width - 1
    return True


def _midi_output_path(state: EditorState) -> str:
    base = "out"
    if state.path:
        base = str(Path(state.path).with_suffix(""))
    return base + ".mid"


def _print_pdf(state: EditorState) -> None:
    base = "out"
    if state.path:
        base = str(Path(state.path).with_suffix(""))
    ly_path = base + ".ly"
    state.message = export_lilypond(
        ly_path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )
    state.message = print_lilypond_pdf(ly_path, output_base=base)


def _play_midi(state: EditorState, start_bar: int | None = None, path: str | None = None) -> None:
    path = path or _midi_output_path(state)
    start_bar = state.cursor_bar if start_bar is None else start_bar
    try:
        bpm = int(state.settings.get("tempo", "90") or "90")
    except ValueError:
        bpm = 90
    state.message = export_midi(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        bpm=bpm,
        start_bar=start_bar,
    )
    state.message = play_midi(path)


def _handle_key(state: EditorState, key: int) -> bool:
    if state.mode == "insert":
        return _handle_insert(state, key)
    if state.mode == "command":
        return _handle_command(state, key)
    if state.mode == "search":
        return _handle_search(state, key)
    if state.mode == "help":
        if key in (ord("q"), ord("Q"), 27):
            state.mode = "normal"
            return True
        if key in (ord("j"), curses.KEY_DOWN):
            state.help_offset += 1
            return True
        if key in (ord("k"), curses.KEY_UP):
            state.help_offset = max(0, state.help_offset - 1)
            return True
        return True
    return _handle_normal(state, key)


def _load_piece(path: str | None) -> Piece:
    if path:
        if path.lower().endswith(".tab"):
            return load_tab(path)
        return load_ft3(path)
    return Piece(title="Untitled", bars=[])


def _main(stdscr: curses.window, path: str | None) -> int:
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(50)

    settings = load_settings(CONFIG_PATH)
    piece = _load_piece(path)
    if not piece.bars:
        piece.bars = [Bar()]

    state = EditorState(piece, settings)
    state.path = path
    try:
        strings = int(settings.get("strings", DEFAULT_SETTINGS["strings"]))
    except ValueError:
        strings = int(DEFAULT_SETTINGS["strings"])
    if 4 <= strings <= 7:
        state.piece.strings = strings
    try:
        spacing = int(settings.get("spacing", DEFAULT_SETTINGS["spacing"]))
    except ValueError:
        spacing = int(DEFAULT_SETTINGS["spacing"])
    state.bar_width = max(4, spacing)
    if piece.bars and piece.bars[0].time_sig:
        state.settings["time"] = piece.bars[0].time_sig or state.settings.get("time", "C")
    if not state.durations:
        state.durations = build_durations(piece)

    running = True
    while running:
        height, width = stdscr.getmaxyx()
        state.screen_height = height
        state.screen_width = width
        state.clamp()
        _ensure_cursor_visible(state, width, height)
        render_piece(
            stdscr,
            state.piece,
            state.bar_offset,
            state.cursor_bar,
            state.cursor_string,
            state.cursor_col,
            state.bar_width,
            state.overrides,
            state.durations,
            state.ornaments,
            state.annotations,
            state.highlights,
            state.slurs,
            state.ties,
            state.holds,
            state.mode,
            state.cmdline,
            state.message,
            _status_line(state),
            state.searchline,
            state.settings,
            export_ascii(
                state.piece,
                state.overrides,
                state.durations,
                state.bar_width,
                settings=state.settings,
                ornaments=state.ornaments,
                annotations=state.annotations,
                slurs=state.slurs,
                ties=state.ties,
                holds=state.holds,
            ).splitlines()
            if state.ascii_preview
            else None,
            state.help_offset,
        )

        key = stdscr.getch()
        if key != -1:
            running = _handle_key(state, key)

    return 0


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    return curses.wrapper(_main, path)


if __name__ == "__main__":
    raise SystemExit(main())
