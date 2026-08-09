from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from oud.editor.core.state import EditorState
from oud.editor.services.media.jobs import start_pdf_job
from oud.editor.editing.primitives.ranges import BarRange
from oud.editor.editing.visual import visual_bar_range

SaveFn = Callable[[str, dict[str, str]], None]
ExportMidiFn = Callable[..., str]
ExportLyFn = Callable[..., str]
ExportMusicXmlFn = Callable[..., str]
ExportMxlFn = Callable[..., str]
StartMidiFn = Callable[..., None]
MidiCommandFn = Callable[..., list[str] | None]
WhichFn = Callable[[str], str | None]


def cmd_midi(
    state: EditorState,
    args: str,
    config_path: str,
    *,
    export_midi_fn: ExportMidiFn,
    save_fn: SaveFn,
) -> None:
    target = args.strip()
    if target:
        path = target
    else:
        base = Path(state.path) if state.path else Path("out")
        path = str(base.with_suffix(".mid"))
    state.message = export_midi_fn(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        dotted=state.dotted,
        ornaments=state.ornaments,
    )
    save_fn(config_path, state.settings)


def cmd_lilypond(
    state: EditorState,
    args: str,
    config_path: str,
    *,
    export_lilypond_fn: ExportLyFn,
    save_fn: SaveFn,
) -> None:
    target = args.strip()
    if target:
        path = target
    else:
        base = Path(state.path) if state.path else Path("out")
        path = str(base.with_suffix(".ly"))
    state.message = export_lilypond_fn(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
    )
    save_fn(config_path, state.settings)


def cmd_musicxml(
    state: EditorState,
    args: str,
    config_path: str,
    *,
    export_musicxml_fn: ExportMusicXmlFn,
    export_mxl_fn: ExportMxlFn,
    save_fn: SaveFn,
) -> None:
    target = args.strip()
    if target:
        path = target
    else:
        base = Path(state.path) if state.path else Path("out")
        path = str(base.with_suffix(".musicxml"))
    if Path(path).suffix.lower() == ".mxl":
        state.message = export_mxl_fn(
            path,
            state.piece,
            state.overrides,
            state.durations,
            state.bar_width,
            settings=state.settings,
            dotted=state.dotted,
        )
    else:
        state.message = export_musicxml_fn(
            path,
            state.piece,
            state.overrides,
            state.durations,
            state.bar_width,
            settings=state.settings,
            dotted=state.dotted,
        )
    save_fn(config_path, state.settings)


def cmd_play(
    state: EditorState,
    args: str,
    config_path: str,
    *,
    start_midi_fn: StartMidiFn,
    save_fn: SaveFn,
) -> None:
    parts = args.split()
    if parts and parts[0] in {"loop", "range", "selection"}:
        _cmd_play_range(state, parts, config_path, start_midi_fn=start_midi_fn, save_fn=save_fn)
        return
    start = int(parts[0]) - 1 if parts and parts[0].isdigit() else None
    tempo = parts[1] if len(parts) > 1 else None
    if tempo:
        state.settings["tempo"] = tempo
    start_midi_fn(state, start_bar=start)
    save_fn(config_path, state.settings)


def _cmd_play_range(
    state: EditorState,
    parts: list[str],
    config_path: str,
    *,
    start_midi_fn: StartMidiFn,
    save_fn: SaveFn,
) -> None:
    bar_range = _playback_bar_range(state)
    if bar_range.is_empty:
        state.message = "No range to play"
        return
    loops = 2
    tempo: str | None = None
    for token in parts[1:]:
        if token.isdigit() and loops == 2:
            loops = max(1, int(token))
        elif token.isdigit():
            tempo = token
    if tempo:
        state.settings["tempo"] = tempo
    start_midi_fn(
        state,
        start_bar=bar_range.start,
        end_bar=bar_range.end - 1,
        loop_count=loops,
    )
    save_fn(config_path, state.settings)


def _playback_bar_range(state: EditorState) -> BarRange:
    if state.visual_anchor is not None:
        return visual_bar_range(state)
    return BarRange.single(state.cursor_bar).clamp(len(state.piece.bars))


def cmd_midicmd(
    state: EditorState,
    target: str,
    *,
    midi_command_fn: MidiCommandFn,
    which_fn: WhichFn,
    platform: str,
) -> None:
    soundfont = state.settings.get("soundfont", "") or None
    cmd = midi_command_fn(
        path=target,
        soundfont=soundfont,
        platform=platform,
        fluidsynth=which_fn("fluidsynth"),
        timidity=which_fn("timidity"),
        opener=which_fn("open") if platform == "darwin" else None,
    )
    if cmd is None:
        state.message = "No MIDI player found"
        return
    state.message = " ".join(cmd)


def cmd_midicmd_default(
    state: EditorState,
    args: str,
    *,
    cmd_midicmd_fn: Callable[[EditorState, str], None],
) -> None:
    target = args.strip() or (state.path or "out.mid")
    cmd_midicmd_fn(state, target)


def print_pdf(
    state: EditorState,
    args: str = "",
    *,
    export_lilypond_fn: ExportLyFn,
    print_lilypond_pdf_fn: Callable[..., str],
) -> None:
    target = args.strip()
    base = str(Path(target).with_suffix("")) if target else "out"
    if not target and state.path:
        base = str(Path(state.path).with_suffix(""))
    ly_path = base + ".ly"
    # PDF output should be readable by default: force full tab notation so
    # stems/flags are visible in LilyPond output, but do not persist this in
    # editor settings/config.
    pdf_settings = dict(state.settings)
    pdf_settings["tabnotation"] = "full"
    state.message = export_lilypond_fn(
        ly_path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=pdf_settings,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )
    start_pdf_job(
        state,
        base + ".pdf",
        lambda: print_lilypond_pdf_fn(
            ly_path,
            base,
            binary=pdf_settings.get("lilypond", "lilypond-2.26"),
        ),
    )
