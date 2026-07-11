from __future__ import annotations

from pathlib import Path

from oud.core.ft3 import load_ft3
from oud.core.musicxml_import import load_musicxml, load_mxl
from oud.core.tab_parser import TabData, load_tab, load_tab_data
from oud.editor.document import configure_document
from oud.editor.insert_session import set_mode
from oud.editor.state import EditorState
from oud.petrucci.model import Piece

LoadResult = tuple[
    Piece,
    dict[tuple[int, int, int], str],
    dict[tuple[int, int, int], int],
    set[tuple[int, int]],
    int | None,
]
TabOpenResult = tuple[
    Piece,
    dict[tuple[int, int, int], str],
    dict[tuple[int, int, int], int],
    set[tuple[int, int]],
    int | None,
    TabData | None,
]


def import_warning_summary(piece: Piece) -> str:
    if not piece.import_warnings:
        return ""
    count = len(piece.import_warnings)
    suffix = f"; {count} total" if count > 1 else ""
    return f"Import warning: {piece.import_warnings[0]} (:info{suffix})"


def _load_tab_for_open(path: str, *, load_tab_data_fn, load_tab_fn) -> TabOpenResult:
    parsed = load_tab_data_fn(path)
    if parsed is None:
        return load_tab_fn(path), {}, {}, set(), None, None
    return (
        parsed.piece,
        parsed.overrides,
        parsed.durations,
        parsed.dotted,
        parsed.bar_width,
        parsed,
    )


def _invalid_load_result(path: str | None, message: str) -> LoadResult:
    title = Path(path).stem if path else "Untitled"
    piece = Piece(title=title, bars=[])
    piece.import_warnings.append(message)
    return piece, {}, {}, set(), None


def load_piece_data(path: str | None) -> LoadResult:  # noqa: PLR0911
    overrides: dict[tuple[int, int, int], str] = {}
    durations: dict[tuple[int, int, int], int] = {}
    dotted: set[tuple[int, int]] = set()
    bar_width: int | None = None
    if path and not Path(path).exists():
        return _invalid_load_result(path, f"Missing file: {path}")
    if path:
        path_obj = Path(path)
        if path_obj.is_dir():
            return _invalid_load_result(path, f"Ignored directory path: {path}")
        try:
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
        except Exception as exc:
            return _invalid_load_result(path, f"Could not open {path_obj.name}: {exc}")
    return Piece(title="Untitled", bars=[]), overrides, durations, dotted, bar_width


def load_piece(path: str | None) -> Piece:
    piece, _overrides, _durations, _dotted, _bar_width = load_piece_data(path)
    return piece


def reset_loaded_file_state(state: EditorState) -> None:
    state.undo_stack.clear()
    state.redo_stack.clear()
    state.undo_group_stack.clear()
    state.annotations.clear()
    state.ornaments.clear()
    state.highlights.clear()
    state.slurs.clear()
    state.ties.clear()
    state.holds.clear()
    state.glisses.clear()
    state._slur_start = None
    state._tie_start = None
    state._hold_start = None
    state.stave_breaks.clear()
    state.marks.clear()
    state.pending_mark = ""
    state.pending_key = ""
    state.pending_find = ""
    state.count_prefix = ""
    state.visual_anchor = None
    state.modified = False
    state.clean_undo_depth = len(state.undo_stack)
    state.pending_quit = False


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
        loaded_piece, overrides, durations, dotted, bar_width, parsed = _load_tab_for_open(
            path,
            load_tab_data_fn=load_tab_data_fn,
            load_tab_fn=load_tab_fn,
        )
        if not loaded_piece.bars and loaded_piece.import_warnings:
            state.message = import_warning_summary(loaded_piece)
            return
        state.piece = loaded_piece
        state.tab_data = parsed
    elif path.lower().endswith(".mxl"):
        state.piece = load_mxl_fn(path)
        state.tab_data = None
    elif path.lower().endswith((".musicxml", ".xml")):
        state.piece = load_musicxml_fn(path)
        state.tab_data = None
    else:
        state.piece = load_ft3_fn(path)
        state.tab_data = None
    state.overrides = overrides
    state.durations = durations
    state.dotted = dotted
    reset_loaded_file_state(state)
    configure_document(state, path, forced_read_only=state.forced_read_only)
    if bar_width:
        state.bar_width = max(4, bar_width)
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_col = 0
    state.bar_offset = 0
    set_mode(state, "normal")
    if not state.durations and build_durations_fn is not None:
        state.durations = build_durations_fn(state.piece)
    state.message = f"Opened {path}"
    if state.piece.import_warnings:
        warning = import_warning_summary(state.piece)
        state.persistent_notice = warning
        state.message = f"{state.message} ({warning})"
