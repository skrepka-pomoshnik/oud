from __future__ import annotations

from oud.core.time_utils import parse_time_signature_value
from oud.editor.controller_utils import string_index
from oud.editor.edit_ops import record_action
from oud.editor.messages import NO_BARS
from oud.editor.state import EditorState, UndoAction


def cmd_time(state: EditorState, value: str) -> None:
    if value in ("auto", "detect"):
        text = "auto"
    else:
        parsed = parse_time_signature_value(value)
        if parsed is None:
            state.message = "Invalid time signature"
            return
        beats, unit = parsed
        text = f"{beats}/{unit}"
    prev_setting = state.settings.get("time")
    prev_bar = None
    state.settings["time"] = text
    if state.piece.bars:
        prev_bar = state.piece.bars[state.cursor_bar].time_sig
        state.piece.bars[state.cursor_bar].time_sig = text
    record_action(
        state,
        UndoAction(
            kind="timesig",
            data={
                "bar": state.cursor_bar,
                "prev": prev_bar,
                "new": text,
                "setting_prev": prev_setting,
                "setting_new": text,
            },
        ),
    )
    state.modified = True
    state.message = f"Time {text}"


def cmd_barline(state: EditorState, value: str) -> None:
    if value not in ("thin", "thick", "double", "hidden", "pale"):
        state.message = "Barline must be thin/thick/double/hidden/pale"
        return
    set_barline(state, value)


def cmd_repeat(state: EditorState, value: str) -> None:
    normalized = "".join(value.strip().lower().replace(".", "").split())
    if normalized not in {
        "none",
        "start",
        "end",
        "dots",
        "both",
        "dc",
        "dacapo",
        "ds",
        "fine",
        "coda",
        "tocoda",
        "dcalfine",
        "dcalcoda",
        "dsalfine",
        "dsalcoda",
    }:
        state.message = (
            "Repeat must be none/start/end/dots/both/dc/ds/fine/coda/"
            "tocoda/dcalfine/dcalcoda/dsalfine/dsalcoda"
        )
        return
    set_repeat(state, normalized)


def cmd_dynamic(state: EditorState, value: str) -> None:
    normalized = value.strip().lower()
    if not normalized:
        state.message = "Dynamic must be clear/ppp/pp/p/mp/mf/f/ff/fff/sfz/rfz"
        return
    set_dynamic(state, normalized)


def cmd_fermata(state: EditorState, value: str) -> None:
    normalized = value.strip().lower() or "toggle"
    if normalized not in {"on", "off", "toggle"}:
        state.message = "Fermata must be on/off/toggle"
        return
    set_fermata(state, normalized)


def set_ornament(state: EditorState, value: str) -> None:
    key = (state.cursor_bar, state.cursor_col)
    prev = state.ornaments.get(key)
    if value == "clear":
        record_action(
            state,
            UndoAction(
                kind="ornament",
                data={"key": key, "prev": prev, "new": None},
            ),
        )
        state.ornaments.pop(key, None)
        state.modified = True
        state.message = "Ornament cleared"
        return
    if len(value) != 1:
        state.message = "Ornament must be 1 char or clear"
        return
    record_action(
        state,
        UndoAction(
            kind="ornament",
            data={"key": key, "prev": prev, "new": value},
        ),
    )
    state.ornaments[key] = value
    state.modified = True
    state.message = f"Ornament {value}"


def set_annotation(state: EditorState, value: str) -> None:
    key = (state.cursor_bar, state.cursor_col)
    prev = state.annotations.get(key)
    if value == "clear":
        record_action(
            state,
            UndoAction(
                kind="annotation",
                data={"key": key, "prev": prev, "new": None},
            ),
        )
        state.annotations.pop(key, None)
        state.modified = True
        state.message = "Annotation cleared"
        return
    new_value = value[:8]
    record_action(
        state,
        UndoAction(
            kind="annotation",
            data={"key": key, "prev": prev, "new": new_value},
        ),
    )
    state.annotations[key] = new_value
    state.modified = True
    state.message = "Annotation set"


def set_highlight(state: EditorState, value: str) -> None:
    key = (state.cursor_bar, string_index(state, state.cursor_string), state.cursor_col)
    if value == "on":
        record_action(
            state,
            UndoAction(
                kind="highlight",
                data={"key": key, "prev": False, "new": True},
            ),
        )
        state.highlights.add(key)
        state.modified = True
        state.message = "Highlight on"
        return
    if value == "off":
        record_action(
            state,
            UndoAction(
                kind="highlight",
                data={"key": key, "prev": True, "new": False},
            ),
        )
        state.highlights.discard(key)
        state.modified = True
        state.message = "Highlight off"
        return
    state.message = "Highlight must be on/off"


def set_barline(state: EditorState, value: str) -> None:
    if not state.piece.bars:
        state.message = NO_BARS
        return
    bar = state.piece.bars[state.cursor_bar]
    prev = bar.barline
    mapping = {
        "thin": "|",
        "thick": "||",
        "double": "||",
        "hidden": " ",
        "pale": ":",
    }
    new = mapping.get(value, "|")
    record_action(
        state,
        UndoAction(
            kind="barline",
            data={"bar": state.cursor_bar, "prev": prev, "new": new},
        ),
    )
    bar.barline = new
    state.modified = True
    state.message = f"Barline {value}"


def set_repeat(state: EditorState, value: str) -> None:
    if not state.piece.bars:
        state.message = NO_BARS
        return
    bar = state.piece.bars[state.cursor_bar]
    prev = bar.repeat
    normalized = "".join(value.strip().lower().replace(".", "").split())
    mapping = {
        "none": "",
        "start": ".:",
        "end": ":.",
        "dots": ".",
        "both": ":|:",
        "dc": "DC",
        "dacapo": "DC",
        "ds": "DS",
        "fine": "Fine",
        "coda": "Coda",
        "tocoda": "To Coda",
        "dcalfine": "DC al Fine",
        "dcalcoda": "DC al Coda",
        "dsalfine": "DS al Fine",
        "dsalcoda": "DS al Coda",
    }
    new = mapping.get(normalized, "")
    structural = new in {".:", ":.", ".", ":|:"}
    if structural and not prev:
        limit = int(state.settings.get("maxrepeats", "30") or 30)
        existing = sum(
            1 for entry in state.piece.bars if entry.repeat in {".:", ":.", ".", ":|:"}
        )
        if existing >= limit:
            state.message = f"Repeat limit {limit} reached"
            return
    record_action(
        state,
        UndoAction(
            kind="repeat",
            data={"bar": state.cursor_bar, "prev": prev, "new": new},
        ),
    )
    bar.repeat = new
    state.modified = True
    state.message = f"Repeat {normalized}"


def set_dynamic(state: EditorState, value: str) -> None:
    if not state.piece.bars:
        state.message = NO_BARS
        return
    normalized = value.strip().lower()
    allowed = {"clear", "ppp", "pp", "p", "mp", "mf", "f", "ff", "fff", "sfz", "rfz"}
    if normalized not in allowed:
        state.message = "Dynamic must be clear/ppp/pp/p/mp/mf/f/ff/fff/sfz/rfz"
        return
    bar = state.piece.bars[state.cursor_bar]
    prev = bar.dynamic
    new = None if normalized == "clear" else normalized
    record_action(
        state,
        UndoAction(
            kind="dynamic",
            data={"bar": state.cursor_bar, "prev": prev, "new": new},
        ),
    )
    bar.dynamic = new
    state.modified = True
    state.message = "Dynamic cleared" if new is None else f"Dynamic {new}"


def set_fermata(state: EditorState, value: str) -> None:
    if not state.piece.bars:
        state.message = NO_BARS
        return
    bar = state.piece.bars[state.cursor_bar]
    prev = bar.fermata
    new = (not prev) if value == "toggle" else (value == "on")
    record_action(
        state,
        UndoAction(
            kind="fermata",
            data={"bar": state.cursor_bar, "prev": prev, "new": new},
        ),
    )
    bar.fermata = new
    state.modified = True
    state.message = "Fermata on" if new else "Fermata off"


def set_slur(state: EditorState, value: str) -> None:
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
            prev = list(state.slurs)
            state.slurs.append((pos[0], start_col, end_col))
            record_action(
                state,
                UndoAction(
                    kind="slurs",
                    data={"prev": prev, "new": list(state.slurs)},
                ),
            )
            state._slur_start = None
            state.modified = True
            state.message = "Slur set"
            return
        state.message = "Slur start not set"
        return
    if value == "clear":
        prev = list(state.slurs)
        state.slurs = [entry for entry in state.slurs if entry[0] != state.cursor_bar]
        record_action(
            state,
            UndoAction(
                kind="slurs",
                data={"prev": prev, "new": list(state.slurs)},
            ),
        )
        state.modified = True
        state.message = "Slur cleared"
        return
    state.message = "Slur must be start/end/clear"


def set_tie(state: EditorState, value: str) -> None:
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
            prev = list(state.ties)
            state.ties.append((pos[0], start_col, end_col))
            record_action(
                state,
                UndoAction(
                    kind="ties",
                    data={"prev": prev, "new": list(state.ties)},
                ),
            )
            state._tie_start = None
            state.modified = True
            state.message = "Tie set"
            return
        state.message = "Tie start not set"
        return
    if value == "clear":
        prev = list(state.ties)
        state.ties = [entry for entry in state.ties if entry[0] != state.cursor_bar]
        record_action(
            state,
            UndoAction(
                kind="ties",
                data={"prev": prev, "new": list(state.ties)},
            ),
        )
        state.modified = True
        state.message = "Tie cleared"
        return
    state.message = "Tie must be start/end/clear"


def set_hold(state: EditorState, value: str) -> None:
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
            prev = list(state.holds)
            state.holds.append((pos[0], start_col, end_col))
            record_action(
                state,
                UndoAction(
                    kind="holds",
                    data={"prev": prev, "new": list(state.holds)},
                ),
            )
            state._hold_start = None
            state.modified = True
            state.message = "Hold set"
            return
        state.message = "Hold start not set"
        return
    if value == "clear":
        prev = list(state.holds)
        state.holds = [entry for entry in state.holds if entry[0] != state.cursor_bar]
        record_action(
            state,
            UndoAction(
                kind="holds",
                data={"prev": prev, "new": list(state.holds)},
            ),
        )
        state.modified = True
        state.message = "Hold cleared"
        return
    state.message = "Hold must be start/end/clear"
