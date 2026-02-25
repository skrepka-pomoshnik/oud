from __future__ import annotations

from pathlib import Path

from oud.core.ft3 import load_ft3
from oud.core.model import Piece
from oud.core.musicxml_import import load_musicxml, load_mxl
from oud.core.tab_parser import load_tab, load_tab_data
from oud.editor.state import EditorState

LoadResult = tuple[
    Piece,
    dict[tuple[int, int, int], str],
    dict[tuple[int, int, int], int],
    set[tuple[int, int]],
    int | None,
]


def load_piece_data(path: str | None) -> LoadResult:  # noqa: PLR0911
    overrides: dict[tuple[int, int, int], str] = {}
    durations: dict[tuple[int, int, int], int] = {}
    dotted: set[tuple[int, int]] = set()
    bar_width: int | None = None
    if path and not Path(path).exists():
        title = Path(path).stem if path else "Untitled"
        piece = Piece(title=title, bars=[])
        return piece, overrides, durations, dotted, bar_width
    if path:
        if path.lower().endswith(".tab"):
            parsed = load_tab_data(path)
            if parsed is not None:
                overrides = parsed.overrides
                durations = parsed.durations
                dotted = parsed.dotted
                bar_width = parsed.bar_width
                return parsed.piece, overrides, durations, dotted, bar_width
            return load_tab(path), overrides, durations, dotted, bar_width
        if path.lower().endswith(".mxl"):
            return load_mxl(path), overrides, durations, dotted, bar_width
        if path.lower().endswith((".musicxml", ".xml")):
            return load_musicxml(path), overrides, durations, dotted, bar_width
        return load_ft3(path), overrides, durations, dotted, bar_width
    return Piece(title="Untitled", bars=[]), overrides, durations, dotted, bar_width


def load_piece(path: str | None) -> Piece:
    piece, _overrides, _durations, _dotted, _bar_width = load_piece_data(path)
    return piece


def cmd_open(
    state: EditorState,
    args: str,
    *,
    no_path_msg: str,
    load_tab_data_fn=load_tab_data,
    load_tab_fn=load_tab,
    load_ft3_fn=load_ft3,
    load_musicxml_fn=load_musicxml,
    load_mxl_fn=load_mxl,
    build_durations_fn=None,
) -> None:
    path = args.strip()
    if not path:
        state.message = no_path_msg
        return
    if Path(path).is_dir():
        state.message = ""
        return
    overrides: dict[tuple[int, int, int], str] = {}
    durations: dict[tuple[int, int, int], int] = {}
    dotted: set[tuple[int, int]] = set()
    bar_width: int | None = None
    if path.lower().endswith(".tab"):
        parsed = load_tab_data_fn(path)
        if parsed is not None:
            state.piece = parsed.piece
            overrides = parsed.overrides
            durations = parsed.durations
            dotted = parsed.dotted
            bar_width = parsed.bar_width
        else:
            state.piece = load_tab_fn(path)
    elif path.lower().endswith(".mxl"):
        state.piece = load_mxl_fn(path)
    elif path.lower().endswith((".musicxml", ".xml")):
        state.piece = load_musicxml_fn(path)
    else:
        state.piece = load_ft3_fn(path)
    state.path = path
    state.settings["filepath"] = path
    state.overrides = overrides
    state.durations = durations
    state.dotted = dotted
    if bar_width:
        state.bar_width = max(4, bar_width)
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_col = 0
    state.bar_offset = 0
    state.mode = "normal"
    if not state.durations and build_durations_fn is not None:
        state.durations = build_durations_fn(state.piece)
    state.message = f"Opened {path}"
    if state.piece.import_warnings:
        state.message = f"{state.message} ({state.piece.import_warnings[0]})"
