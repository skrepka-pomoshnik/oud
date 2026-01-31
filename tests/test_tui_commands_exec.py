import subprocess
from pathlib import Path

import pytest

from oud.core.model import Bar, Chord, Note, Piece
from oud.core.tab_parser import TabData
from oud.editor import command_ops as cmd_ops
from oud.editor.state import EditorState
from oud.tui import commands as cmd


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
        "spacingmode": "packed",
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
        "frenche": "normal",
    }
    state = EditorState(piece, settings)
    state.screen_width = 80
    return state


def test_apply_command_quit_flow(tmp_path: Path) -> None:
    state = _state()
    state.modified = True
    cmd.apply_command(state, "q", str(tmp_path / "cfg.toml"))
    assert state.pending_quit is True
    assert "Unsaved changes" in state.message
    with pytest.raises(SystemExit):
        cmd.apply_command(state, "q", str(tmp_path / "cfg.toml"))
    with pytest.raises(SystemExit):
        cmd.apply_command(state, "q!", str(tmp_path / "cfg.toml"))


def test_apply_command_unknown_and_wq(tmp_path: Path) -> None:
    state = _state()
    target = tmp_path / "out.tab"
    with pytest.raises(SystemExit):
        cmd.apply_command(state, f"wq {target}", str(tmp_path / "cfg.toml"))
    assert target.exists()
    cmd.apply_command(state, "nope", str(tmp_path / "cfg.toml"))
    assert state.message == "Unknown command: nope"


def test_cmd_set_and_convert(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()
    saved: dict[str, str] = {}

    def _save(_path: str, settings: dict[str, str]) -> None:
        saved.update(settings)

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(
        state,
        "strings=7 style=italian grid=on showdur=on frenchc=alt frenche=tail",
        str(tmp_path / "cfg.toml"),
    )
    assert state.settings["strings"] == "7"
    assert state.settings["style"] == "italian"
    assert state.settings["grid"] == "on"
    assert state.settings["showdur"] == "on"
    assert state.settings["frenchc"] == "alt"
    assert state.settings["frenche"] == "tail"
    assert saved["strings"] == "7"
    state.overrides[(0, 0, 0)] = "0"
    cmd.cmd_convert(state, "french", str(tmp_path / "cfg.toml"))
    assert state.settings["style"] == "french"

def test_cmd_set_many_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(
        state,
        "measures=every measuresstep=2 tuning=renaissance "
        "flagstyle=italian time=3/2 key=D countdots=on keys=vim "
        "spacing=10 spacingmode=spread flagredundant=off maxbars=4 maxchords=6 "
        "linelen=60 bargap=2 staffthick=2 fontstyle=baroque charstyle=historic "
        "title=Title author=Author composer=Composer midipatch=12 midigate=70 "
        "soundfont=sf2 tempo=120 grid=on showextras=on showtactus=on italianorient=reverse "
        "maxrepeats=30",
        str(tmp_path / "cfg.toml"),
    )
    assert state.settings["measures"] == "every"
    assert state.settings["measuresstep"] == "2"
    assert state.settings["tuning"] == "g2c3f3a3d4g4"
    assert state.settings["flagstyle"] == "italian"
    assert state.settings["time"] == "3/2"
    assert state.settings["key"] == "D"
    assert state.settings["countdots"] == "on"
    assert state.settings["keys"] == "vim"
    assert state.settings["spacing"] == "10"
    assert state.settings["spacingmode"] == "spread"
    assert state.settings["flagredundant"] == "off"
    assert state.settings["maxbars"] == "4"
    assert state.settings["maxchords"] == "6"
    assert state.settings["linelen"] == "60"
    assert state.settings["bargap"] == "2"
    assert state.settings["staffthick"] == "2"
    assert state.settings["fontstyle"] == "baroque"
    assert state.settings["charstyle"] == "historic"
    assert state.settings["midipatch"] == "12"
    assert state.settings["midigate"] == "70"
    assert state.settings["soundfont"] == "sf2"
    assert state.settings["tempo"] == "120"
    assert state.settings["grid"] == "on"
    assert state.settings["showextras"] == "on"
    assert state.settings["showtactus"] == "on"
    assert state.settings["italianorient"] == "reverse"
    assert state.settings["maxrepeats"] == "30"
    assert state.piece.title == "Title"
    assert state.piece.author == "Author"
    assert state.piece.composer == "Composer"


def test_cmd_ascii_and_midicmd(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _state()
    cmd.cmd_ascii(state, "on")
    assert state.ascii_preview is True
    cmd.cmd_ascii(state, "off")
    assert state.ascii_preview is False
    monkeypatch.setattr(cmd_ops.shutil, "which", lambda _name: None)
    cmd.cmd_midicmd(state, "")
    assert state.message == "No MIDI player found"

def test_cmd_open_tab_and_ft3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()
    tab_piece = Piece(title="Tab", bars=[Bar()], strings=6)
    tab_data = TabData(tab_piece, {(0, 0, 0): "a"}, {(0, 0, 0): 4}, set(), 8)
    monkeypatch.setattr("oud.editor.command_ops.load_tab_data", lambda _path: tab_data)
    cmd.cmd_open(state, str(tmp_path / "file.tab"))
    assert state.piece.title == "Tab"
    assert state.bar_width == 8
    monkeypatch.setattr("oud.editor.command_ops.load_tab_data", lambda _path: None)
    monkeypatch.setattr("oud.editor.command_ops.load_tab", lambda _path: tab_piece)
    cmd.cmd_open(state, str(tmp_path / "other.tab"))
    assert state.piece.title == "Tab"
    ft3_piece = Piece(title="Ft3", bars=[Bar()], strings=6)
    monkeypatch.setattr("oud.editor.command_ops.load_ft3", lambda _path: ft3_piece)
    cmd.cmd_open(state, str(tmp_path / "file.ft3"))
    assert state.piece.title == "Ft3"


def test_cmd_write_and_ascii(tmp_path: Path) -> None:
    state = _state()
    out_tab = tmp_path / "out.tab"
    cmd.cmd_write(state, str(out_tab))
    assert out_tab.exists()
    out_txt = tmp_path / "out.txt"
    cmd.cmd_write_ascii(state, str(out_txt))
    content = out_txt.read_text(encoding="utf-8")
    assert content
    state.screen_width = 40
    state.screen_height = 8
    cmd.cmd_write_ascii(state, str(out_txt))
    lines = out_txt.read_text(encoding="utf-8").splitlines()
    assert len(lines) == state.screen_height
    assert all(len(line) == state.screen_width for line in lines)


def test_cmd_bar_and_chord() -> None:
    state = _state()
    cmd.cmd_bar(state, "add")
    assert len(state.piece.bars) == 3
    cmd.cmd_bar(state, "del")
    assert len(state.piece.bars) == 2
    cmd.cmd_chord(state, "insert")
    assert state.piece.bars[state.cursor_bar].chords
    cmd.cmd_chord(state, "delete")
    assert state.piece.bars[state.cursor_bar].chords == []
    cmd.cmd_chord(state, "other")
    assert state.message == "Chord action: add/del"


def test_cmd_stave_variants() -> None:
    state = _state(bars=4)
    cmd.cmd_stave(state, "break")
    assert state.message == "Stave break added"
    cmd.cmd_stave(state, "join")
    assert state.message == "Stave break removed"
    cmd.cmd_stave(state, "new")
    assert state.message == "Stave inserted"
    state.stave_breaks.add(2)
    state.cursor_bar = 0
    cmd.cmd_stave(state, "del")
    assert state.message == "Stave deleted"
    cmd.cmd_stave(state, "other")
    assert state.message == "Stave action: break/join/new/del"


def test_cmd_time_and_verify() -> None:
    state = _state()
    cmd.cmd_time(state, "bad")
    assert state.message == "Invalid time signature"
    cmd.cmd_time(state, "3/4")
    assert state.piece.bars[state.cursor_bar].time_sig == "3/4"
    state.piece.bars[0].chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
        for _ in range(4)
    ]
    state.settings["time"] = "4/4"
    cmd.cmd_verify(state, "")
    assert state.message == "Measure ok"
    state.piece.bars[0].chords = [Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]
    cmd.cmd_verify(state, "")
    assert state.message.startswith("Underfull")


def test_cmd_midi_lilypond_pdf_play_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = _state()

    def _export_midi(_path: str, *_args: object, **_kwargs: object) -> str:
        return "Midi ok"

    def _export_lilypond(_path: str, *_args: object, **_kwargs: object) -> str:
        return "Ly ok"

    def _print_pdf(_path: str) -> str:
        return "Pdf ok"

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    def _start_midi(state: EditorState, start_bar: int | None = None, path: str | None = None) -> None:
        state.message = f"Played {start_bar} {path}"

    monkeypatch.setattr(cmd_ops, "export_midi", _export_midi)
    monkeypatch.setattr(cmd_ops, "export_lilypond", _export_lilypond)
    monkeypatch.setattr(cmd_ops, "print_lilypond_pdf", _print_pdf)
    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    monkeypatch.setattr("oud.editor.midi_control.start_midi", _start_midi)

    cmd.cmd_midi(state, "", str(tmp_path / "cfg.toml"))
    assert state.message == "Midi ok"
    cmd.cmd_lilypond(state, "", str(tmp_path / "cfg.toml"))
    assert state.message == "Ly ok"
    cmd.cmd_pdf(state, "", str(tmp_path / "cfg.toml"))
    assert state.message == "Pdf ok"
    cmd.cmd_play(state, "2 120", str(tmp_path / "cfg.toml"))
    assert state.settings["tempo"] == "120"
    assert state.message.startswith("Played 1")

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
    cmd.cmd_tool(state, "unknown", str(tmp_path / "cfg.toml"))
    assert state.message == "Tool: reflow|gridflags|flagstyle|comments"
    cmd.cmd_barline(state, "thin")
    cmd.cmd_barline(state, "nope")
    assert state.message == "Barline must be thin/thick/double/hidden/pale"
    cmd.cmd_repeat(state, "start")
    cmd.cmd_repeat(state, "bad")
    assert state.message == "Repeat must be none/start/end/dots"
