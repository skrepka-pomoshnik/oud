# ruff: noqa: PLC0415
from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys

from core.ft3 import build_durations, load_ft3
from core.render_utils import note_type_to_denom
from core.tab_parser import load_tab, load_tab_data
from editor.commands import (
    cmd_author,
    cmd_composer,
    cmd_footnote,
    cmd_header_template,
    cmd_subtitle,
    cmd_title,
)
from editor.ops import (
    delete_chord,
    french_to_fret,
    fret_to_french,
    fret_to_italian,
    insert_chord,
    italian_to_fret,
)
from editor.state import EditorState, UndoAction
from exports.export_tab import export_ascii, export_tab_to_file
from exports.lilypond import export_lilypond, print_lilypond_pdf
from exports.midi import _midi_command, export_midi, play_midi
from settings import save_settings


def _parse_time_sig_value(text: str) -> tuple[int, int] | None:
    value = text.strip()
    if value in ("C", "c"):
        return 4, 4
    if value in ("O", "o"):
        return 3, 4
    if "/" in value:
        parts = value.split("/", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            beats = int(parts[0])
            unit = int(parts[1])
            if beats > 0 and unit > 0:
                return beats, unit
    return None


def _tuning_preset(value: str) -> str | None:
    presets = {
        "renaissance": "g2c3f3a3d4g4",
        "guitar": "e4a3d3f+3b2e2",
        "dminor": "a4b-4c4d4e4f4g4a3d3f3a2d2f2",
        "sharp": "c4d4e4f+4g4a3d3g3b2d2f+2",
        "flat": "c4d4e-4f4g4a3d3g3a+2d2f2",
    }
    return presets.get(value)


def start_midi(state: EditorState, start_bar: int | None = None, path: str | None = None) -> None:
    if state.midi_proc is not None and state.midi_proc.poll() is None:
        state.midi_proc.terminate()
        state.midi_proc = None
    path = path or (str(os.path.splitext(state.path)[0]) if state.path else "out") + ".mid"
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
        dotted=state.dotted,
    )
    soundfont = state.settings.get("soundfont", "") or None
    state.message, state.midi_proc = play_midi(path, soundfont=soundfont)


def _bar_duration_sum(
    state: EditorState,
    bar_index: int,
    default_duration: int,
) -> float:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return 0.0
    bar = state.piece.bars[bar_index]
    total = 0.0
    if bar.chords:
        for chord in bar.chords:
            denom = note_type_to_denom(chord.note_type) or default_duration
            duration = 4.0 / denom
            if chord.dotted:
                duration *= 1.5
            total += duration
        return total
    last = None
    for col in range(state.bar_width):
        found = None
        for s_idx in range(state.piece.strings):
            key = (bar_index, s_idx, col)
            if key in state.durations:
                denom = state.durations[key]
                if found is None or denom > found:
                    found = denom
        if found is None:
            found = default_duration
        if found != last:
            duration = 4.0 / found
            if (bar_index, col) in state.dotted:
                duration *= 1.5
            total += duration
            last = found
    return total


def _record_action(state: EditorState, action: UndoAction) -> None:
    state.undo_stack.append(action)
    state.redo_stack.clear()
    state.modified = True


def _record_undo(
    state: EditorState,
    kind: str,
    key: tuple[int, int, int],
    prev: object | None,
    new: object | None,
) -> None:
    _record_action(
        state,
        UndoAction(
            kind=kind,
            data={"key": key, "prev": prev, "new": new},
        ),
    )


def _apply_duration(state: EditorState, key: tuple[int, int, int], dur: int) -> None:
    bar, _string, col = key
    prev = {k: v for k, v in state.durations.items() if k[0] == bar and k[2] == col}
    for prev_key in prev:
        state.durations.pop(prev_key, None)
    new_key = (bar, 0, col)
    state.durations[new_key] = dur
    _record_action(
        state,
        UndoAction(
            kind="duration_col",
            data={"bar": bar, "col": col, "prev": prev, "new": {new_key: dur}},
        ),
    )


def _convert_overrides(state: EditorState, target_style: str) -> None:
    converted = 0
    skipped = 0
    items = list(state.overrides.items())
    for key, ch in items:
        if target_style == "italian":
            fret = french_to_fret(ch)
            out = fret_to_italian(fret) if fret is not None else None
        else:
            fret = italian_to_fret(ch)
            out = fret_to_french(fret) if fret is not None else None
        if out is None:
            skipped += 1
            continue
        state.overrides[key] = out
        converted += 1
    state.message = f"Converted {converted}, skipped {skipped}"


def apply_set_command(state: EditorState, args: str, config_path: str) -> None:  # noqa: PLR0912
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
            if count < 4 or count > 13:
                state.message = "Strings must be 4-13"
                continue
            state.piece.strings = count
            state.cursor_string = min(state.cursor_string, count - 1)
            state.settings["strings"] = str(count)
        elif key == "style":
            if value not in ("french", "italian"):
                state.message = "Style must be french or italian"
                continue
            current = state.settings.get("style", "french")
            if value != current:
                _convert_overrides(state, value)
            state.settings["style"] = value
        elif key == "measures":
            if value not in ("start", "every", "five"):
                state.message = "Measures must be start/every/five"
                continue
            state.settings["measures"] = value
        elif key == "measuresstep":
            if not value.isdigit() or int(value) < 1:
                state.message = "Measuresstep must be >=1"
                continue
            state.settings["measuresstep"] = value
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
            if value not in ("vim", "vim+arrows", "casual", "casual+arrows"):
                state.message = "Keys must be vim/vim+arrows/casual/casual+arrows"
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
        elif key == "spacingmode":
            if value not in ("packed", "spread", "auto"):
                state.message = "Spacingmode must be packed/spread/auto"
                continue
            state.settings["spacingmode"] = value
        elif key == "flagredundant":
            if value not in ("on", "off"):
                state.message = "Flagredundant must be on/off"
                continue
            state.settings["flagredundant"] = value
        elif key == "maxbars":
            if not value.isdigit():
                state.message = "Maxbars must be int"
                continue
            state.settings["maxbars"] = value
        elif key == "maxchords":
            if not value.isdigit():
                state.message = "Maxchords must be int"
                continue
            state.settings["maxchords"] = value
        elif key == "linelen":
            if not value.isdigit():
                state.message = "Linelen must be int"
                continue
            state.settings["linelen"] = value
        elif key == "bargap":
            if not value.isdigit():
                state.message = "Bargap must be int"
                continue
            state.settings["bargap"] = value
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
        elif key == "title":
            state.piece.title = value
            state.modified = True
        elif key == "author":
            state.piece.author = value
            state.modified = True
        elif key == "composer":
            state.piece.composer = value
            state.modified = True
        elif key == "midipatch":
            if not value.isdigit():
                state.message = "Midipatch must be int"
                continue
            state.settings["midipatch"] = value
        elif key == "midigate":
            if not value.isdigit():
                state.message = "Midigate must be int"
                continue
            state.settings["midigate"] = value
        elif key == "soundfont":
            state.settings["soundfont"] = value
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
    save_settings(config_path, state.settings)


def cmd_open(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path:
        state.message = "No path"
        return
    overrides: dict[tuple[int, int, int], str] = {}
    durations: dict[tuple[int, int, int], int] = {}
    dotted: set[tuple[int, int]] = set()
    bar_width: int | None = None
    if path.lower().endswith(".tab"):
        parsed = load_tab_data(path)
        if parsed is not None:
            state.piece = parsed.piece
            overrides = parsed.overrides
            durations = parsed.durations
            dotted = parsed.dotted
            bar_width = parsed.bar_width
        else:
            state.piece = load_tab(path)
    else:
        state.piece = load_ft3(path)
    state.path = path
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
    if not state.durations:
        state.durations = build_durations(state.piece)
    state.message = f"Opened {path}"


def cmd_set(state: EditorState, args: str, config_path: str) -> None:
    apply_set_command(state, args.strip(), config_path)


def cmd_convert(state: EditorState, args: str, config_path: str) -> None:
    target = args.strip()
    if target not in ("french", "italian"):
        state.message = "Convert target must be french or italian"
        return
    _convert_overrides(state, target)
    state.settings["style"] = target
    save_settings(config_path, state.settings)


def cmd_ascii(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("on", "off"):
        state.message = "Ascii must be on/off"
        return
    state.ascii_preview = value == "on"
    state.message = f"Ascii preview {value}"


def cmd_midi(state: EditorState, args: str, config_path: str) -> None:
    target = args.strip()
    if target:
        path = target
    else:
        base = str(os.path.splitext(state.path)[0]) if state.path else "out"
        path = base + ".mid"
    state.message = export_midi(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        dotted=state.dotted,
    )
    save_settings(config_path, state.settings)


def cmd_lilypond(state: EditorState, args: str, config_path: str) -> None:
    target = args.strip()
    if target:
        path = target
    else:
        base = str(os.path.splitext(state.path)[0]) if state.path else "out"
        path = base + ".ly"
    state.message = export_lilypond(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
    )
    save_settings(config_path, state.settings)


def cmd_pdf(state: EditorState, _args: str, config_path: str) -> None:
    cmd_lilypond(state, "", config_path)
    state.message = print_lilypond_pdf(state.path or "out.ly")


def cmd_play(state: EditorState, args: str, config_path: str) -> None:
    parts = args.split()
    start = int(parts[0]) - 1 if parts and parts[0].isdigit() else None
    tempo = parts[1] if len(parts) > 1 else None
    if tempo:
        state.settings["tempo"] = tempo
    start_midi(state, start_bar=start)
    save_settings(config_path, state.settings)


def cmd_orn(state: EditorState, args: str) -> None:
    _set_ornament(state, args.strip())


def cmd_annot(state: EditorState, args: str) -> None:
    _set_annotation(state, args.strip())


def cmd_highlight(state: EditorState, args: str) -> None:
    _set_highlight(state, args.strip())


def cmd_chord(state: EditorState, args: str) -> None:
    value = args.strip()
    if value in ("ins", "insert"):
        bar = state.piece.bars[state.cursor_bar]
        prev = copy.deepcopy(bar.chords)
        insert_chord(bar, state.bar_width, state.cursor_col)
        _record_action(
            state,
            UndoAction(
                kind="chords",
                data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
            ),
        )
        return
    if value in ("del", "delete", "remove"):
        bar = state.piece.bars[state.cursor_bar]
        prev = copy.deepcopy(bar.chords)
        if delete_chord(bar, state.bar_width, state.cursor_col):
            _record_action(
                state,
                UndoAction(
                    kind="chords",
                    data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
                ),
            )
        return
    state.message = "Chord action: insert/delete"


def cmd_midicmd(state: EditorState, _args: str) -> None:
    path = state.path or "out.mid"
    soundfont = state.settings.get("soundfont", "") or None
    cmd = _midi_command(
        path=path,
        soundfont=soundfont,
        platform=sys.platform,
        fluidsynth=shutil.which("fluidsynth"),
        timidity=shutil.which("timidity"),
        opener=shutil.which("open") if sys.platform == "darwin" else None,
    )
    state.message = " ".join(cmd) if cmd else "No MIDI player"


def cmd_source(state: EditorState, args: str) -> None:
    target = args.strip() or state.path
    if not target:
        state.message = "No source path"
        return
    viewer = shutil.which("less")
    if not viewer:
        state.message = "Missing less"
        return
    subprocess.run([viewer, target], check=False)  # noqa: S603


def cmd_info(state: EditorState, _args: str) -> None:
    state.mode = "info"
    state.info_offset = 0


def cmd_bar(state: EditorState, args: str) -> None:
    from app import _bars_per_line, _delete_bar, _insert_bar, _snapshot_bar, _system_range

    action = args.strip() or "add"
    bars_per_line = _bars_per_line(state, state.screen_width or 80)
    start, end = _system_range(state, state.cursor_bar, bars_per_line)
    if action in ("add", "after"):
        index = state.cursor_bar + 1
        prev_breaks = set(state.stave_breaks)
        _insert_bar(state, index)
        _record_action(
            state,
            UndoAction(
                kind="bar-insert",
                data={"index": index, "prev": prev_breaks, "new": set(state.stave_breaks)},
            ),
        )
        state.cursor_bar = index
        state.cursor_col = 0
        state.message = "Bar added"
        return
    if action in ("before", "insert"):
        index = state.cursor_bar
        prev_breaks = set(state.stave_breaks)
        _insert_bar(state, index)
        _record_action(
            state,
            UndoAction(
                kind="bar-insert",
                data={"index": index, "prev": prev_breaks, "new": set(state.stave_breaks)},
            ),
        )
        state.cursor_bar = index
        state.cursor_col = 0
        state.message = "Bar inserted"
        return
    if action in ("del", "delete", "remove"):
        index = state.cursor_bar
        if start == end:
            snapshot = _snapshot_bar(state, index)
            prev_breaks = set(state.stave_breaks)
            _delete_bar(state, state.cursor_bar)
            new_breaks = set(state.stave_breaks)
            _record_action(
                state,
                UndoAction(
                    kind="bar-delete",
                    data={
                        "index": index,
                        "snapshot": snapshot,
                        "prev": prev_breaks,
                        "new": new_breaks,
                    },
                ),
            )
        else:
            snapshot = _snapshot_bar(state, index)
            prev_breaks = set(state.stave_breaks)
            _delete_bar(state, state.cursor_bar)
            new_breaks = set(state.stave_breaks)
            _record_action(
                state,
                UndoAction(
                    kind="bar-delete",
                    data={
                        "index": index,
                        "snapshot": snapshot,
                        "prev": prev_breaks,
                        "new": new_breaks,
                    },
                ),
            )
        state.cursor_bar = min(state.cursor_bar, len(state.piece.bars) - 1)
        state.cursor_col = 0
        state.message = "Bar deleted"
        return
    state.message = "Bar action: add/after/before/insert/del"


def cmd_stave(state: EditorState, args: str) -> None:
    from app import _bars_per_line, _delete_bar, _insert_bar, _snapshot_bar, _system_range

    action = args.strip() or "break"
    bars_per_line = _bars_per_line(state, state.screen_width or 80)
    start, end = _system_range(state, state.cursor_bar, bars_per_line)
    if action in ("break", "split"):
        idx = state.cursor_bar + 1
        if idx < len(state.piece.bars):
            prev = set(state.stave_breaks)
            state.stave_breaks.add(idx)
            _record_action(
                state,
                UndoAction(
                    kind="stave-breaks",
                    data={"prev": prev, "new": set(state.stave_breaks)},
                ),
            )
            state.message = "Stave break added"
        else:
            state.message = "No bar to break after"
        return
    if action in ("join", "merge"):
        idx = state.cursor_bar + 1
        if idx in state.stave_breaks:
            prev = set(state.stave_breaks)
            state.stave_breaks.discard(idx)
            _record_action(
                state,
                UndoAction(
                    kind="stave-breaks",
                    data={"prev": prev, "new": set(state.stave_breaks)},
                ),
            )
            state.message = "Stave break removed"
        else:
            state.message = "No break at cursor"
        return
    if action in ("new", "insert"):
        idx = state.cursor_bar + 1
        prev_breaks = set(state.stave_breaks)
        _insert_bar(state, idx)
        state.stave_breaks.add(idx)
        _record_action(
            state,
            UndoAction(
                kind="bar-insert",
                data={"index": idx, "prev": prev_breaks, "new": set(state.stave_breaks)},
            ),
        )
        state.message = "Stave inserted"
        return
    if action in ("del", "delete", "remove"):
        if start >= end:
            state.message = "No stave to delete"
            return
        snapshots = [_snapshot_bar(state, idx) for idx in range(start, end)]
        prev_breaks = set(state.stave_breaks)
        for _ in range(end - start):
            _delete_bar(state, start)
        new_breaks = set(state.stave_breaks)
        _record_action(
            state,
            UndoAction(
                kind="stave-delete",
                data={
                    "start": start,
                    "snapshots": snapshots,
                    "prev": prev_breaks,
                    "new": new_breaks,
                },
            ),
        )
        state.cursor_bar = min(state.cursor_bar, len(state.piece.bars) - 1)
        state.cursor_col = 0
        state.message = "Stave deleted"
        return
    state.message = "Stave action: break/join/new/del"


def cmd_slur(state: EditorState, args: str) -> None:
    _set_slur(state, args.strip())


def cmd_tie(state: EditorState, args: str) -> None:
    _set_tie(state, args.strip())


def cmd_hold(state: EditorState, args: str) -> None:
    _set_hold(state, args.strip())


def cmd_barline(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("thin", "thick", "double", "hidden", "pale"):
        state.message = "Barline must be thin/thick/double/hidden/pale"
        return
    _set_barline(state, value)


def cmd_repeat(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("none", "start", "end", "dots"):
        state.message = "Repeat must be none/start/end/dots"
        return
    _set_repeat(state, value)


def cmd_tool(state: EditorState, args: str, config_path: str) -> None:
    action = args.strip() or "reflow"
    if action == "reflow":
        prev = set(state.stave_breaks)
        state.stave_breaks.clear()
        _record_action(
            state,
            UndoAction(
                kind="stave-breaks",
                data={"prev": prev, "new": set(state.stave_breaks)},
            ),
        )
        state.message = "Reflowed (breaks cleared)"
        return
    if action == "gridflags":
        current = state.settings.get("flagstyle", "standard")
        next_value = "board" if current != "board" else "standard"
        state.settings["flagstyle"] = next_value
        save_settings(config_path, state.settings)
        state.message = f"Flagstyle {next_value}"
        return
    if action == "comments":
        prev = dict(state.annotations)
        state.annotations.clear()
        _record_action(
            state,
            UndoAction(
                kind="annotations-all",
                data={"prev": prev, "new": dict(state.annotations)},
            ),
        )
        state.message = "Annotations cleared"
        return
    state.message = "Tool: reflow|gridflags|comments"


def cmd_time(state: EditorState, args: str) -> None:
    parsed = _parse_time_sig_value(args)
    if parsed is None:
        state.message = "Invalid time signature"
        return
    beats, unit = parsed
    value = f"{beats}/{unit}"
    prev_setting = state.settings.get("time")
    prev_bar = None
    state.settings["time"] = value
    if state.piece.bars:
        prev_bar = state.piece.bars[state.cursor_bar].time_sig
        state.piece.bars[state.cursor_bar].time_sig = value
    _record_action(
        state,
        UndoAction(
            kind="timesig",
            data={
                "bar": state.cursor_bar,
                "prev": prev_bar,
                "new": value,
                "setting_prev": prev_setting,
                "setting_new": value,
            },
        ),
    )
    state.modified = True
    state.message = f"Time {value}"


def cmd_verify(state: EditorState, _args: str) -> None:
    parsed = _parse_time_sig_value(state.settings.get("time", "C"))
    if parsed is None:
        state.message = "No valid time signature"
        return
    beats, unit = parsed
    expected = beats * (4.0 / unit)
    total = _bar_duration_sum(state, state.cursor_bar, default_duration=4)
    delta = total - expected
    if abs(delta) < 0.01:
        state.message = "Measure ok"
        return
    if delta > 0:
        state.message = f"Overfull by {delta:.2f} beats"
    else:
        state.message = f"Underfull by {abs(delta):.2f} beats"


def cmd_undo(state: EditorState, _args: str) -> None:
    from app import _undo

    _undo(state)


def cmd_redo(state: EditorState, _args: str) -> None:
    from app import _redo

    _redo(state)


def cmd_write(state: EditorState, args: str) -> None:
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


def cmd_write_ascii(state: EditorState, args: str) -> None:
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


def _set_ornament(state: EditorState, value: str) -> None:
    from app import _set_ornament as _set_ornament_impl

    _set_ornament_impl(state, value)


def _set_annotation(state: EditorState, value: str) -> None:
    from app import _set_annotation as _set_annotation_impl

    _set_annotation_impl(state, value)


def _set_highlight(state: EditorState, value: str) -> None:
    from app import _set_highlight as _set_highlight_impl

    _set_highlight_impl(state, value)


def _set_slur(state: EditorState, value: str) -> None:
    from app import _set_slur as _set_slur_impl

    _set_slur_impl(state, value)


def _set_tie(state: EditorState, value: str) -> None:
    from app import _set_tie as _set_tie_impl

    _set_tie_impl(state, value)


def _set_hold(state: EditorState, value: str) -> None:
    from app import _set_hold as _set_hold_impl

    _set_hold_impl(state, value)


def _set_barline(state: EditorState, value: str) -> None:
    from app import _set_barline as _set_barline_impl

    _set_barline_impl(state, value)


def _set_repeat(state: EditorState, value: str) -> None:
    from app import _set_repeat as _set_repeat_impl

    _set_repeat_impl(state, value)


def apply_command(state: EditorState, cmdline: str, config_path: str) -> None:
    cmdline = cmdline.strip()
    if not cmdline:
        return
    if cmdline in ("q", "quit", "q!", "quit!"):
        raise SystemExit(0)
    cmd, *rest = cmdline.split(maxsplit=1)
    args = rest[0] if rest else ""
    handlers = {
        "e": lambda s, a: cmd_open(s, a),
        "set": lambda s, a: cmd_set(s, a, config_path),
        "convert": lambda s, a: cmd_convert(s, a, config_path),
        "ascii": lambda s, a: cmd_ascii(s, a),
        "midi": lambda s, a: cmd_midi(s, a, config_path),
        "lilypond": lambda s, a: cmd_lilypond(s, a, config_path),
        "pdf": lambda s, a: cmd_pdf(s, a, config_path),
        "print": lambda s, a: cmd_pdf(s, a, config_path),
        "play": lambda s, a: cmd_play(s, a, config_path),
        "orn": lambda s, a: cmd_orn(s, a),
        "annot": lambda s, a: cmd_annot(s, a),
        "highlight": lambda s, a: cmd_highlight(s, a),
        "midicmd": lambda s, a: cmd_midicmd(s, a),
        "source": lambda s, a: cmd_source(s, a),
        "info": lambda s, a: cmd_info(s, a),
        "bar": lambda s, a: cmd_bar(s, a),
        "chord": lambda s, a: cmd_chord(s, a),
        "stave": lambda s, a: cmd_stave(s, a),
        "slur": lambda s, a: cmd_slur(s, a),
        "tie": lambda s, a: cmd_tie(s, a),
        "hold": lambda s, a: cmd_hold(s, a),
        "barline": lambda s, a: cmd_barline(s, a),
        "repeat": lambda s, a: cmd_repeat(s, a),
        "tool": lambda s, a: cmd_tool(s, a, config_path),
        "time": lambda s, a: cmd_time(s, a),
        "timesig": lambda s, a: cmd_time(s, a),
        "verify": lambda s, a: cmd_verify(s, a),
        "title": lambda s, a: cmd_title(s, a),
        "author": lambda s, a: cmd_author(s, a),
        "composer": lambda s, a: cmd_composer(s, a),
        "subtitle": lambda s, a: cmd_subtitle(s, a),
        "footnote": lambda s, a: cmd_footnote(s, a),
        "header": lambda s, a: cmd_header_template(s, a),
        "undo": lambda s, a: cmd_undo(s, a),
        "redo": lambda s, a: cmd_redo(s, a),
        "w": lambda s, a: cmd_write(s, a),
        "wa": lambda s, a: cmd_write_ascii(s, a),
        "write": lambda s, a: cmd_write(s, a),
    }
    handler = handlers.get(cmd)
    if handler is None:
        if cmd in ("wq", "x"):
            cmd_write(state, args)
            if state.message.startswith("Wrote "):
                raise SystemExit(0)
            return
        state.message = f"Unknown command: {cmdline}"
        return
    handler(state, args)
