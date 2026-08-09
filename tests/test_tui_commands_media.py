import subprocess
import zipfile
from pathlib import Path
from typing import cast

import pytest

from oud.editor.commands import dispatch as cmd_ops
from oud.editor.core.state import EditorState
from oud.presentation.tui import commands as cmd
from petrucci.core.model import Bar, Piece


def _state(bars: int = 2) -> EditorState:
    piece = Piece(title="T", bars=[Bar() for _ in range(bars)], strings=6)
    settings = {
        "style": "french",
        "measures": "start",
        "tuning": "g2c3f3a3d4g4",
        "strings": "6",
        "flagstyle": "standard",
        "time": "C",
        "key": "C",
        "countdots": "off",
        "keys": "vim+arrows",
        "spacing": "12",
        "layout": "packed",
        "linelen": "80",
        "bargap": "1",
        "staffthick": "1",
        "fontstyle": "modern",
        "charstyle": "standard",
        "midipatch": "24",
        "tempo": "90",
        "soundfont": "",
        "grid": "off",
        "showdur": "off",
        "showextras": "off",
        "showtactus": "off",
        "italianorient": "normal",
        "frenchc": "normal",
    }
    state = EditorState(piece, settings)
    state.screen_width = 80
    return state


def _wait_pdf(state: EditorState) -> None:
    job = state.pdf_job
    assert job is not None
    job.join(timeout=1)
    assert not job.is_alive()


def test_cmd_midi_lilypond_pdf_play_source(  # noqa: C901
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = _state()

    def _export_midi(_path: str, *_args: object, **_kwargs: object) -> str:
        return "Midi ok"

    def _export_lilypond(_path: str, *_args: object, **_kwargs: object) -> str:
        return "Ly ok"

    def _export_musicxml(_path: str, *_args: object, **_kwargs: object) -> str:
        return "Xml ok"

    def _export_mxl(_path: str, *_args: object, **_kwargs: object) -> str:
        return "Mxl ok"

    pdf_called: dict[str, str] = {}

    def _print_pdf(_path: str, _base: str | None = None, **_kwargs: object) -> str:
        pdf_called["path"] = _path
        return "Pdf ok"

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    def _start_midi(state: EditorState, start_bar: int | None = None, path: str | None = None) -> None:
        state.message = f"Played {start_bar} {path}"

    monkeypatch.setattr(cmd_ops, "export_midi", _export_midi)
    monkeypatch.setattr(cmd_ops, "export_lilypond", _export_lilypond)
    monkeypatch.setattr(cmd_ops, "export_musicxml", _export_musicxml)
    monkeypatch.setattr(cmd_ops, "export_mxl", _export_mxl)
    monkeypatch.setattr(cmd_ops, "print_lilypond_pdf", _print_pdf)
    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    monkeypatch.setattr("oud.editor.services.media.midi.start_midi", _start_midi)

    cmd.cmd_midi(state, "", str(tmp_path / "cfg.toml"))
    assert state.message == "Midi ok"
    cmd.cmd_lilypond(state, "", str(tmp_path / "cfg.toml"))
    assert state.message == "Ly ok"
    cmd.apply_command(state, "musicxml out.musicxml", str(tmp_path / "cfg.toml"))
    assert state.message == "Xml ok"
    cmd.apply_command(state, "musicxml out.mxl", str(tmp_path / "cfg.toml"))
    assert state.message == "Mxl ok"
    state.path = str(tmp_path / "score.ft3")
    cmd.cmd_pdf(state, "", str(tmp_path / "cfg.toml"))
    _wait_pdf(state)
    assert state.message == "Pdf ok"
    assert pdf_called["path"].endswith("score.ly")
    cmd.cmd_play(state, "2 120", str(tmp_path / "cfg.toml"))
    assert state.settings["tempo"] == "120"
    assert state.message.startswith("Played 1")

    state.path = None
    cmd.cmd_source(state, "")
    assert state.message == "No source path"
    state.path = str(tmp_path / "src.tab")
    monkeypatch.setattr(cmd_ops.shutil, "which", lambda _name: "/usr/bin/less")
    ran: dict[str, list[str]] = {}

    def _run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        ran["args"] = args
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(cmd_ops.subprocess, "run", _run)
    cmd.cmd_source(state, "")
    assert ran["args"][0].endswith("less")
    cmd.cmd_tool(state, "gridflags", str(tmp_path / "cfg.toml"))
    cmd.cmd_tool(state, "comments", str(tmp_path / "cfg.toml"))
    cmd.cmd_tool(state, "reflow", str(tmp_path / "cfg.toml"))


def test_cmd_tool_comments_gridflags_and_reflow(tmp_path: Path) -> None:
    state = _state(bars=3)
    state.annotations[(0, 1)] = "comment"
    state.stave_breaks = {1, 2}

    cmd.cmd_tool(state, "comments", str(tmp_path / "cfg.toml"))
    assert state.annotations == {}
    assert state.message == "Annotations cleared"

    cmd.cmd_tool(state, "gridflags", str(tmp_path / "cfg.toml"))
    assert state.settings["flagstyle"] == "board"
    assert state.message == "Flagstyle board"

    cmd.cmd_tool(state, "reflow", str(tmp_path / "cfg.toml"))
    assert state.stave_breaks == set()
    assert state.message == "Reflowed (breaks cleared)"


def test_cmd_play_loop_uses_visual_or_cursor_range(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = _state(bars=4)
    calls: list[dict[str, int | None]] = []

    def _start_midi(  # noqa: PLR0917 - mirrors the legacy playback callback
        state: EditorState,
        start_bar: int | None = None,
        path: str | None = None,
        bpm: int | None = None,
        end_bar: int | None = None,
        loop_count: int = 1,
    ) -> None:
        _ = (state, path, bpm)
        calls.append(
            {
                "start_bar": start_bar,
                "end_bar": end_bar,
                "loop_count": loop_count,
            },
        )

    monkeypatch.setattr("oud.editor.services.media.midi.start_midi", _start_midi)

    state.cursor_bar = 2
    cmd.cmd_play(state, "loop", str(tmp_path / "cfg.toml"))
    assert calls[-1] == {"start_bar": 2, "end_bar": 2, "loop_count": 2}

    state.visual_anchor = (1, 0, 0)
    state.cursor_bar = 3
    cmd.cmd_play(state, "loop 3", str(tmp_path / "cfg.toml"))
    assert calls[-1] == {"start_bar": 1, "end_bar": 3, "loop_count": 3}


def test_cmd_pdf_real_ft3_path_uses_neighbor_ly_output_if_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    src = Path("tests/fixtures/ft3/corpus/czarna_krowa.ft3")
    if not src.exists():
        pytest.skip("local FT3 corpus file not available")
    state = _state()
    state.path = str(src)
    called: dict[str, str] = {}

    def _export_lilypond(path: str, *_args: object, **_kwargs: object) -> str:
        called["ly"] = path
        return f"Wrote {path}"

    def _print_pdf(path: str, _base: str | None = None, **_kwargs: object) -> str:
        called["pdf"] = path
        return f"Printed {Path(path).with_suffix('.pdf')}"

    monkeypatch.setattr(cmd_ops, "export_lilypond", _export_lilypond)
    monkeypatch.setattr(cmd_ops, "print_lilypond_pdf", _print_pdf)
    monkeypatch.setattr(cmd_ops, "save_settings", lambda *_args, **_kwargs: None)

    cmd.cmd_pdf(state, "", str(tmp_path / "cfg.toml"))
    _wait_pdf(state)
    assert called["ly"].endswith("czarna_krowa.ly")
    assert called["pdf"].endswith("czarna_krowa.ly")
    assert state.message.endswith("czarna_krowa.pdf")


def test_cmd_pdf_forces_full_tabnotation_only_for_pdf_export(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = _state()
    state.path = str(tmp_path / "score.ft3")
    state.settings["tabnotation"] = "minimal"
    captured: dict[str, object] = {}

    def _export_lilypond(
        _path: str,
        *_args: object,
        **kwargs: object,
    ) -> str:
        captured["settings"] = kwargs["settings"]
        return "Ly ok"

    def _print_pdf(_ly_path: str, _base: str | None = None, **_kwargs: object) -> str:
        return "Pdf ok"

    monkeypatch.setattr(cmd_ops, "export_lilypond", _export_lilypond)
    monkeypatch.setattr(cmd_ops, "print_lilypond_pdf", _print_pdf)

    cmd.cmd_pdf(state, "", str(tmp_path / "cfg.toml"))
    _wait_pdf(state)
    assert state.message == "Pdf ok"
    exported_settings_obj = captured["settings"]
    exported_settings = cast("dict[str, str]", exported_settings_obj)
    assert exported_settings["tabnotation"] == "full"
    # Editor settings are not mutated/persisted by :pdf defaulting behavior.
    assert state.settings["tabnotation"] == "minimal"
    cmd.cmd_tool(state, "unknown", str(tmp_path / "cfg.toml"))
    assert state.message == "Tool: reflow|gridflags|flagstyle|comments"
    cmd.cmd_barline(state, "thin")
    cmd.cmd_barline(state, "nope")
    assert state.message == "Barline must be thin/thick/double/hidden/pale"
    cmd.cmd_repeat(state, "start")
    assert state.piece.bars[state.cursor_bar].repeat == ".:"
    cmd.cmd_repeat(state, "dc al fine")
    assert state.piece.bars[state.cursor_bar].repeat == "DC al Fine"
    cmd.cmd_repeat(state, "bad")
    assert state.message == (
        "Repeat must be none/start/end/dots/both/dc/ds/fine/coda/tocoda/dcalfine/dcalcoda/dsalfine/dsalcoda"
    )
    cmd.apply_command(state, "ending 1,2", str(tmp_path / "cfg.toml"))
    assert state.piece.bars[state.cursor_bar].ending_numbers == (1, 2)
    cmd.apply_command(state, "ending clear", str(tmp_path / "cfg.toml"))
    assert state.piece.bars[state.cursor_bar].ending_numbers == ()
    cmd.cmd_dynamic(state, "mf")
    assert state.piece.bars[state.cursor_bar].dynamic == "mf"
    cmd.cmd_dynamic(state, "clear")
    assert state.piece.bars[state.cursor_bar].dynamic is None
    cmd.cmd_fermata(state, "on")
    assert state.piece.bars[state.cursor_bar].fermata is True
    cmd.cmd_fermata(state, "toggle")
    assert state.piece.bars[state.cursor_bar].fermata is False
    cmd.cmd_dynamic(state, "bad")
    assert state.message == "Dynamic must be clear/ppp/pp/p/mp/mf/f/ff/fff/sfz/rfz"
    cmd.cmd_fermata(state, "bad")
    assert state.message == "Fermata must be on/off/toggle"


def test_tui_notation_commands_export_to_musicxml_and_mxl(tmp_path: Path) -> None:
    state = _state(bars=1)
    cfg = str(tmp_path / "cfg.toml")
    cmd.apply_command(state, "time 3/4", cfg)
    cmd.apply_command(state, "repeat dcalfine", cfg)
    cmd.apply_command(state, "barline double", cfg)
    xml_path = tmp_path / "score.musicxml"
    cmd.apply_command(state, f"musicxml {xml_path}", cfg)
    text = xml_path.read_text(encoding="utf-8")
    assert "<beats>3</beats>" in text
    assert "<beat-type>4</beat-type>" in text
    assert "<words>D.C. al Fine</words>" in text
    assert "<bar-style>light-light</bar-style>" in text
    mxl_path = tmp_path / "score.mxl"
    cmd.apply_command(state, f"musicxml {mxl_path}", cfg)
    with zipfile.ZipFile(mxl_path) as zf:
        names = set(zf.namelist())
        assert "mimetype" in names
        assert "META-INF/container.xml" in names
        assert any(name.endswith(".xml") for name in names)


def test_apply_command_dispatch_executes_all_registered_specs(  # noqa: C901
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = _state()
    calls: list[str] = []

    def _record2(name: str):
        def _stub(_state: EditorState, _args: str) -> None:
            calls.append(name)

        return _stub

    def _record3(name: str):
        def _stub(_state: EditorState, _args: str, _cfg: str) -> None:
            calls.append(name)

        return _stub

    patched_2arg = {
        "cmd_open",
        "cmd_write",
        "cmd_write_ascii",
        "cmd_ascii",
        "cmd_title",
        "cmd_author",
        "cmd_composer",
        "cmd_subtitle",
        "cmd_footnote",
        "cmd_header_template",
        "cmd_orn",
        "cmd_annot",
        "cmd_highlight",
        "cmd_midicmd",
        "cmd_source",
        "cmd_help",
        "cmd_info",
        "cmd_ack",
        "cmd_notes",
        "cmd_plugins",
        "cmd_bar",
        "cmd_cursor",
        "cmd_col",
        "cmd_chord",
        "cmd_stave",
        "cmd_slur",
        "cmd_tie",
        "cmd_hold",
        "cmd_barline",
        "cmd_repeat",
        "cmd_ending",
        "cmd_dynamic",
        "cmd_fermata",
        "cmd_arpeggio",
        "cmd_separee",
        "cmd_tuplet",
        "cmd_transpose",
        "cmd_retune",
        "cmd_courseshift",
        "cmd_time",
        "cmd_verify",
        "cmd_vocal",
        "cmd_pause",
    }
    patched_3arg = {
        "cmd_set",
        "cmd_dark",
        "cmd_light",
        "cmd_convert",
        "cmd_midi",
        "cmd_play",
        "cmd_lilypond",
        "cmd_musicxml",
        "cmd_pdf",
        "cmd_tool",
        "cmd_undo",
        "cmd_redo",
    }
    for name in patched_2arg:
        monkeypatch.setattr(cmd, name, _record2(name))
    for name in patched_3arg:
        monkeypatch.setattr(cmd, name, _record3(name))
    cmd._command_specs.cache_clear()
    cmd._command_map.cache_clear()
    out_path = tmp_path / "out.tab"
    xml_path = tmp_path / "out.musicxml"
    arg_map = {
        "e": str(out_path),
        "w": str(out_path),
        "wa": str(tmp_path / "out.txt"),
        "wascii": str(tmp_path / "out.txt"),
        "writeascii": str(tmp_path / "out.txt"),
        "saveascii": str(tmp_path / "out.txt"),
        "write": str(out_path),
        "ascii": "on",
        "midi": str(tmp_path / "out.mid"),
        "play": "1 120",
        "lilypond": str(tmp_path / "out.ly"),
        "musicxml": str(xml_path),
        "pdf": str(tmp_path / "out.pdf"),
        "print": str(tmp_path / "out.pdf"),
        "set": "showdur=on",
        "convert": "french",
        "time": "3/4",
        "timesig": "4/4",
        "verify": "",
        "title": "Title",
        "author": "Author",
        "composer": "Composer",
        "subtitle": "Subtitle",
        "footnote": "Footnote",
        "header": "",
        "undo": "",
        "redo": "",
        "orn": "#",
        "annot": "x",
        "highlight": "mark",
        "midicmd": "fluidsynth",
        "source": "",
        "info": "",
        "notes": "",
        "plugins": "",
        "bar": "add",
        "cursor": "1 1 1",
        "col": "1",
        "chord": "insert",
        "stave": "break",
        "slur": "0 0 0",
        "tie": "0 0 0",
        "hold": "0 0 0",
        "barline": "thin",
        "repeat": "start",
        "ending": "1,2",
        "dynamic": "mf",
        "fermata": "on",
        "arpeggio": "on",
        "separee": "on",
        "tuplet": "3",
        "transpose": "2",
        "retune": "guitar",
        "courseshift": "down",
        "vocal": "clear",
        "tool": "gridflags",
    }
    specs = cmd._command_specs()
    for spec in specs:
        args = arg_map.get(spec.name, "")
        line = spec.name if not args else f"{spec.name} {args}"
        cmd.apply_command(state, line, str(tmp_path / "cfg.toml"))
        assert not state.message.startswith("Unknown command")
    assert len(calls) == len(specs)
    cmd._command_specs.cache_clear()
    cmd._command_map.cache_clear()
