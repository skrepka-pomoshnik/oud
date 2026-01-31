from __future__ import annotations

import copy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from oud.core.ft3 import build_durations, load_ft3
from oud.core.help_text import help_lines
from oud.core.tab_parser import load_tab, load_tab_data
from oud.core.time_utils import parse_time_signature_value
from oud.core.tuning_utils import tuning_preset
from oud.editor.bar_ops import clear_bar_contents, delete_bar, insert_bar, snapshot_bar
from oud.editor.controller_utils import string_index
from oud.editor.edit_ops import apply_override, record_action
from oud.editor.layout import bars_per_line, system_range
from oud.editor.messages import MISSING_LESS, NO_BARS, NO_PATH, NO_SOURCE_PATH
from oud.editor.ops import (
    delete_chord,
    french_to_fret,
    fret_to_french,
    fret_to_italian,
    insert_chord,
    italian_to_fret,
)
from oud.editor.state import EditorState, UndoAction, YankedBar
from oud.exports.export_tab import export_ascii, export_tab_to_file
from oud.exports.lilypond import export_lilypond, print_lilypond_pdf
from oud.exports.midi import _midi_command, export_midi
from oud.settings import save_settings


def row_first_note_col(state: EditorState) -> int:
    bar = state.cursor_bar
    string = string_index(state, min(state.cursor_string, state.piece.strings - 1))
    cols = [col for (b, s, col) in state.overrides if b == bar and s == string]
    if not cols:
        return 0
    return min(cols)


def tuning_preset_value(value: str) -> str | None:
    return tuning_preset(value)


def parse_time_signature(text: str) -> tuple[int, int] | None:
    return parse_time_signature_value(text)


def show_help(state: EditorState) -> None:
    viewer = shutil.which("less")
    if not viewer:
        state.message = MISSING_LESS
        return
    content = "\n".join(help_lines()) + "\n"
    if state.mode == "plugin" and state.plugin_name:
        root = Path(__file__).resolve().parents[1]
        plugin_help = root / "plugins" / f"{state.plugin_name}.txt"
        if plugin_help.exists():
            content = plugin_help.read_text(encoding="utf-8") + "\n"
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as temp:
        temp.write(content)
        temp_path = Path(temp.name)
    try:
        if state.suspend_tui:
            state.suspend_tui()
        subprocess.run([viewer, str(temp_path)], check=False)  # noqa: S603
    finally:
        if state.resume_tui:
            state.resume_tui()
        temp_path.unlink(missing_ok=True)


def yank_bar(state: EditorState, index: int) -> None:
    if index < 0 or index >= len(state.piece.bars):
        return
    bar_copy = copy.deepcopy(state.piece.bars[index])
    overrides = {
        (0, s, c): value
        for (b, s, c), value in state.overrides.items()
        if b == index
    }
    durations = {
        (0, s, c): value
        for (b, s, c), value in state.durations.items()
        if b == index
    }
    annotations = {(0, c): value for (b, c), value in state.annotations.items() if b == index}
    ornaments = {(0, c): value for (b, c), value in state.ornaments.items() if b == index}
    dotted = {(0, c) for (b, c) in state.dotted if b == index}
    slurs = [(0, start, end) for (b, start, end) in state.slurs if b == index]
    ties = [(0, start, end) for (b, start, end) in state.ties if b == index]
    holds = [(0, start, end) for (b, start, end) in state.holds if b == index]
    state.yanked_bar = YankedBar(
        bar=bar_copy,
        overrides=overrides,
        durations=durations,
        annotations=annotations,
        ornaments=ornaments,
        dotted=dotted,
        slurs=slurs,
        ties=ties,
        holds=holds,
    )


def paste_bar(state: EditorState, index: int) -> None:
    if state.yanked_bar is None:
        state.message = "No yanked bar"
        return
    insert_bar(state, index)
    bar_copy = copy.deepcopy(state.yanked_bar.bar)
    state.piece.bars[index] = bar_copy
    for (b, s, c), value in state.yanked_bar.overrides.items():
        state.overrides[(index + b, s, c)] = value
    for (b, s, c), value in state.yanked_bar.durations.items():
        state.durations[(index + b, s, c)] = value
    for (b, c), value in state.yanked_bar.annotations.items():
        state.annotations[(index + b, c)] = value
    for (b, c), value in state.yanked_bar.ornaments.items():
        state.ornaments[(index + b, c)] = value
    for (b, c) in state.yanked_bar.dotted:
        state.dotted.add((index + b, c))
    for b, start, end in state.yanked_bar.slurs:
        state.slurs.append((index + b, start, end))
    for b, start, end in state.yanked_bar.ties:
        state.ties.append((index + b, start, end))
    for b, start, end in state.yanked_bar.holds:
        state.holds.append((index + b, start, end))
    state.modified = True


def cmd_bar(state: EditorState, args: str) -> None:
    action = args.strip() or "add"
    if action in ("add", "after"):
        prev_breaks = set(state.stave_breaks)
        insert_bar(state, state.cursor_bar + 1)
        new_breaks = set(state.stave_breaks)
        record_action(
            state,
            UndoAction(
                kind="bar-insert",
                data={"index": state.cursor_bar + 1, "prev": prev_breaks, "new": new_breaks},
            ),
        )
        state.cursor_bar = min(state.cursor_bar + 1, len(state.piece.bars) - 1)
        state.cursor_col = 0
        state.message = "Bar added"
        return
    if action in ("before", "insert"):
        prev_breaks = set(state.stave_breaks)
        insert_bar(state, state.cursor_bar)
        new_breaks = set(state.stave_breaks)
        record_action(
            state,
            UndoAction(
                kind="bar-insert",
                data={"index": state.cursor_bar, "prev": prev_breaks, "new": new_breaks},
            ),
        )
        state.cursor_col = 0
        state.message = "Bar inserted"
        return
    if action in ("del", "delete", "remove"):
        if not state.piece.bars:
            state.message = NO_BARS
            return
        index = state.cursor_bar
        if len(state.piece.bars) == 1:
            snapshot = snapshot_bar(state, index)
            clear_bar_contents(state, index)
            record_action(
                state,
                UndoAction(
                    kind="bar-clear",
                    data={"index": index, "snapshot": snapshot},
                ),
            )
        else:
            snapshot = snapshot_bar(state, index)
            prev_breaks = set(state.stave_breaks)
            delete_bar(state, state.cursor_bar)
            new_breaks = set(state.stave_breaks)
            record_action(
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
    action = args.strip() or "break"
    per_line = bars_per_line(state, state.screen_width or 80)
    start, end = system_range(state, state.cursor_bar, per_line)
    if action in ("break", "split"):
        idx = state.cursor_bar + 1
        if idx < len(state.piece.bars):
            prev = set(state.stave_breaks)
            state.stave_breaks.add(idx)
            record_action(
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
            record_action(
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
        insert_bar(state, idx)
        state.stave_breaks.add(idx)
        record_action(
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
        snapshots = [snapshot_bar(state, idx) for idx in range(start, end)]
        prev_breaks = set(state.stave_breaks)
        for _ in range(end - start):
            delete_bar(state, start)
        state.stave_breaks = {
            b - (end - start) if b >= end else b
            for b in state.stave_breaks
            if b < start or b >= end
        }
        record_action(
            state,
            UndoAction(
                kind="bars-delete",
                data={
                    "start": start,
                    "count": end - start,
                    "snapshots": snapshots,
                    "prev": prev_breaks,
                    "new": set(state.stave_breaks),
                },
            ),
        )
        state.cursor_bar = max(0, min(start, len(state.piece.bars) - 1))
        state.cursor_col = 0
        state.message = "Stave deleted"
        return
    state.message = "Stave action: break/join/new/del"


def cmd_open(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path:
        state.message = NO_PATH
        return
    if Path(path).is_dir():
        state.message = ""
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


def cmd_convert(state: EditorState, args: str, config_path: str) -> None:
    target = args.strip()
    if target not in ("french", "italian"):
        state.message = "Convert target must be french or italian"
        return
    convert_overrides(state, target)
    state.settings["style"] = target
    save_settings(config_path, state.settings)
    state.message = f"Converted to {target}"


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
        base = Path(state.path) if state.path else Path("out")
        path = str(base.with_suffix(".mid"))
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
        base = Path(state.path) if state.path else Path("out")
        path = str(base.with_suffix(".ly"))
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
    from oud.editor.midi_control import start_midi  # noqa: PLC0415

    parts = args.split()
    start = int(parts[0]) - 1 if parts and parts[0].isdigit() else None
    tempo = parts[1] if len(parts) > 1 else None
    if tempo:
        state.settings["tempo"] = tempo
    start_midi(state, start_bar=start)
    save_settings(config_path, state.settings)


def apply_set_command(state: EditorState, args: str, config_path: str) -> None:  # noqa: PLR0912, C901
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
                convert_overrides(state, value)
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
            preset = tuning_preset(value)
            state.settings["tuning"] = preset if preset else value
        elif key == "showtuning":
            if value not in ("on", "off"):
                state.message = "Showtuning must be on/off"
                continue
            state.settings["showtuning"] = value
        elif key == "flagstyle":
            allowed = {
                "standard",
                "italian",
                "thin",
                "board",
                "capirola",
                "englishgrid",
                "continental",
            }
            if value not in allowed:
                state.message = (
                    "Flagstyle must be standard/italian/thin/board/capirola/englishgrid/continental"
                )
                continue
            state.settings["flagstyle"] = value
        elif key == "flagstems":
            if value not in ("single", "double"):
                state.message = "Flagstems must be single/double"
                continue
            state.settings["flagstems"] = value
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
        elif key == "spacingfill":
            if value not in ("stretch", "center", "compact", "smart"):
                state.message = "Spacingfill must be stretch/center/compact/smart"
                continue
            state.settings["spacingfill"] = value
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
        elif key == "barsperline":
            if not value.isdigit():
                state.message = "Barsperline must be int"
                continue
            state.settings["barsperline"] = value
        elif key == "maxchords":
            if not value.isdigit():
                state.message = "Maxchords must be int"
                continue
            state.settings["maxchords"] = value
        elif key == "maxrepeats":
            if not value.isdigit():
                state.message = "Maxrepeats must be int"
                continue
            state.settings["maxrepeats"] = value
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
        elif key == "basslabels":
            if value not in ("numeric", "slash", "tuning"):
                state.message = "Basslabels must be numeric/slash/tuning"
                continue
            state.settings["basslabels"] = value
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
        elif key == "italianmultifret":
            if value not in ("on", "off"):
                state.message = "Italianmultifret must be on/off"
                continue
            state.settings["italianmultifret"] = value
        elif key == "viewinvert":
            if value not in ("on", "off"):
                state.message = "Viewinvert must be on/off"
                continue
            state.settings["viewinvert"] = value
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


def cmd_set(state: EditorState, args: str, config_path: str) -> None:
    apply_set_command(state, args.strip(), config_path)


def convert_overrides(state: EditorState, target_style: str) -> None:
    converted = 0
    skipped = 0
    items = list(state.overrides.items())
    for key, ch in items:
        if target_style == "italian":
            if ch == "k":
                out = "x"
            else:
                fret = french_to_fret(ch)
                out = fret_to_italian(fret) if fret is not None else None
        elif ch == "x":
            out = "k"
        else:
            fret = italian_to_fret(ch)
            out = fret_to_french(fret) if fret is not None else None
        if out is None:
            skipped += 1
            continue
        apply_override(state, key, out)
        converted += 1
    state.message = f"Converted {converted}, skipped {skipped}"


def cmd_midicmd(state: EditorState, target: str) -> None:
    soundfont = state.settings.get("soundfont", "") or None
    cmd = _midi_command(
        path=target,
        soundfont=soundfont,
        platform=sys.platform,
        fluidsynth=shutil.which("fluidsynth"),
        timidity=shutil.which("timidity"),
        opener=shutil.which("open") if sys.platform == "darwin" else None,
    )
    if cmd is None:
        state.message = "No MIDI player found"
        return
    state.message = " ".join(cmd)


def cmd_midicmd_default(state: EditorState, args: str) -> None:
    target = args.strip() or (state.path or "out.mid")
    cmd_midicmd(state, target)


def cmd_source(state: EditorState, target: str) -> None:
    path = target.strip() or state.path
    if not path:
        state.message = NO_SOURCE_PATH
        return
    viewer = shutil.which("less")
    if not viewer:
        state.message = MISSING_LESS
        return
    subprocess.run([viewer, path], check=False)  # noqa: S603


def cmd_info(state: EditorState) -> None:
    state.mode = "info"
    state.info_offset = 0


def cmd_plugins(state: EditorState) -> None:
    from oud.editor.plugin_ops import enter_plugin_mode  # noqa: PLC0415

    enter_plugin_mode(state)


def cmd_tool(state: EditorState, action: str, config_path: str) -> None:
    value = action.strip() or "reflow"
    if value == "reflow":
        prev = set(state.stave_breaks)
        state.stave_breaks.clear()
        record_action(
            state,
            UndoAction(
                kind="stave-breaks",
                data={"prev": prev, "new": set(state.stave_breaks)},
            ),
        )
        state.message = "Reflowed (breaks cleared)"
        return
    if value == "gridflags":
        current = state.settings.get("flagstyle", "standard")
        next_value = "board" if current != "board" else "standard"
        state.settings["flagstyle"] = next_value
        save_settings(config_path, state.settings)
        state.message = f"Flagstyle {next_value}"
        return
    if value in ("flagstyle", "flagstyles", "flagcycle"):
        styles = [
            "standard",
            "thin",
            "board",
            "italian",
            "capirola",
            "englishgrid",
            "continental",
        ]
        current = state.settings.get("flagstyle", "standard")
        try:
            idx = styles.index(current)
        except ValueError:
            idx = -1
        next_value = styles[(idx + 1) % len(styles)]
        state.settings["flagstyle"] = next_value
        save_settings(config_path, state.settings)
        state.message = f"Flagstyle {next_value}"
        return
    if value == "comments":
        prev = dict(state.annotations)
        state.annotations.clear()
        record_action(
            state,
            UndoAction(
                kind="annotations-all",
                data={"prev": prev, "new": dict(state.annotations)},
            ),
        )
        state.message = "Annotations cleared"
        return
    state.message = "Tool: reflow|gridflags|flagstyle|comments"


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
    if value not in ("none", "start", "end", "dots"):
        state.message = "Repeat must be none/start/end/dots"
        return
    set_repeat(state, value)


def cmd_verify(state: EditorState) -> None:
    from oud.editor.verify_ops import verify_bar  # noqa: PLC0415

    state.message = verify_bar(state, state.cursor_bar)


def cmd_write(state: EditorState, path: str) -> None:
    export_tab_to_file(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        dotted=state.dotted,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )
    state.modified = False
    state.pending_quit = False
    state.message = f"Wrote {path}"


def cmd_write_default(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path and state.path:
        path = state.path if state.path.endswith(".tab") else state.path + ".tab"
    if not path:
        state.message = "No path for write"
        return
    cmd_write(state, path)


def cmd_write_ascii(state: EditorState, path: str) -> None:
    content = ""
    if state.screen_width > 0 and state.screen_height > 0:
        from oud.editor.status import status_line  # noqa: PLC0415
        from oud.ui.framebuffer import FrameBuffer  # noqa: PLC0415
        from oud.ui.render import render_piece  # noqa: PLC0415

        frame = FrameBuffer(state.screen_height, state.screen_width)
        render_piece(
            frame,
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
            state.dotted,
            state.slurs,
            state.ties,
            state.holds,
            state.mode,
            state.cmdline,
            state.message,
            status_line(state),
            state.searchline,
            state.settings,
            None,
            state.stave_breaks,
            state.plugin_title,
            [
                f"{item.title}{'/' if item.is_dir else ''}"
                for item in state.plugin_items
            ],
            state.plugin_index,
            state.plugin_offset,
            state.help_offset if state.mode != "info" else state.info_offset,
        )
        content = "\n".join(frame.snapshot().lines) + "\n"
    else:
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
    with Path(path).open("w", encoding="utf-8") as f:
        f.write(content)
    state.modified = False
    state.pending_quit = False
    state.message = f"Wrote {path}"


def cmd_write_ascii_default(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path and state.path:
        path = state.path if state.path.endswith(".txt") else state.path + ".txt"
    if not path:
        state.message = "No path for wa"
        return
    cmd_write_ascii(state, path)


def cmd_orn(state: EditorState, args: str) -> None:
    set_ornament(state, args.strip())


def cmd_annot(state: EditorState, args: str) -> None:
    set_annotation(state, args.strip())


def cmd_highlight(state: EditorState, args: str) -> None:
    set_highlight(state, args.strip())


def cmd_chord(state: EditorState, args: str) -> None:
    action = args.strip() or "add"
    if not state.piece.bars:
        state.message = NO_BARS
        return
    bar = state.piece.bars[state.cursor_bar]
    if action in ("add", "insert"):
        prev = copy.deepcopy(bar.chords)
        insert_chord(bar, state.bar_width, state.cursor_col)
        record_action(
            state,
            UndoAction(
                kind="chords",
                data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
            ),
        )
        state.modified = True
        state.message = "Chord added"
        return
    if action in ("del", "delete", "remove"):
        prev = copy.deepcopy(bar.chords)
        if delete_chord(bar, state.bar_width, state.cursor_col):
            record_action(
                state,
                UndoAction(
                    kind="chords",
                    data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
                ),
            )
            state.modified = True
            state.message = "Chord deleted"
        else:
            state.message = "No chord at cursor"
        return
    state.message = "Chord action: add/del"


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
    mapping = {
        "none": "",
        "start": ".:",
        "end": ":.",
        "dots": ".",
    }
    new = mapping.get(value, "")
    if new and not prev:
        limit = int(state.settings.get("maxrepeats", "30") or 30)
        existing = sum(1 for b in state.piece.bars if b.repeat)
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
    state.message = f"Repeat {value}"


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
        state.slurs = [s for s in state.slurs if s[0] != state.cursor_bar]
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
        state.ties = [s for s in state.ties if s[0] != state.cursor_bar]
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
        state.holds = [s for s in state.holds if s[0] != state.cursor_bar]
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


def print_pdf(state: EditorState) -> None:
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
