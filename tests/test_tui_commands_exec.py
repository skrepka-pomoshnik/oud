import subprocess
import zipfile
from pathlib import Path

import pytest

from oud.core.model import Bar, Chord, Note, Piece
from oud.core.tab_parser import TabData
from oud.editor import command_ops as cmd_ops
from oud.editor.file_ops import render_ascii_snapshot
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
        "strings=7 style=italian grid=on showdur=on frenchc=alt",
        str(tmp_path / "cfg.toml"),
    )
    assert state.settings["strings"] == "7"
    assert state.settings["style"] == "italian"
    assert state.settings["grid"] == "on"
    assert state.settings["showdur"] == "on"
    assert state.settings["frenchc"] == "alt"
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
        "spacing=10 layout=spread flagredundant=off maxbars=4 barsperline=3 barpad=2 maxchords=6 "
        "chordwrap=12 "
        "linelen=60 bargap=2 staffthick=2 fontstyle=baroque charstyle=historic "
        "title=Title author=Author composer=Composer midipatch=12 midigate=70 "
        "soundfont=sf2 tempo=120 grid=on showextras=on showtactus=on italianorient=reverse "
        "maxrepeats=30 scrollmode=page beatsnap=soft timesigstyle=fraction "
        "minimumfret=2 maxstretch=5 restrainopenstrings=on",
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
    assert state.settings["layout"] == "spread"
    assert state.settings["flagredundant"] == "off"
    assert state.settings["maxbars"] == "4"
    assert state.settings["barsperline"] == "3"
    assert state.settings["barpad"] == "2"
    assert state.settings["maxchords"] == "6"
    assert state.settings["chordwrap"] == "12"
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
    assert state.settings["scrollmode"] == "page"
    assert state.settings["beatsnap"] == "soft"
    assert state.settings["timesigstyle"] == "fraction"
    assert state.settings["minimumfret"] == "2"
    assert state.settings["maxstretch"] == "5"
    assert state.settings["restrainopenstrings"] == "on"
    assert state.piece.title == "Title"
    assert state.piece.author == "Author"
    assert state.piece.composer == "Composer"


def test_cmd_set_layout_stretch_alias(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "layout=stretch", str(tmp_path / "cfg.toml"))
    assert state.settings["layout"] == "auto"
    assert state.settings["justify"] == "edge"


def test_cmd_set_tabnotation_full_preset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "tabnotation=full", str(tmp_path / "cfg.toml"))
    assert state.settings["tabnotation"] == "full"
    assert state.settings["showdur"] == "on"
    assert state.settings["showextras"] == "on"
    assert state.settings["showtactus"] == "on"
    assert state.settings["flagredundant"] == "off"
    assert state.settings["timesigstyle"] == "fraction"
    assert state.settings["tiecuestyle"] == "paren"
    assert state.settings["showft3extras"] == "on"
    assert state.settings["slurcuestyle"] == "paren"
    assert state.settings["holdcuestyle"] == "angle"
    assert state.settings["glisscuestyle"] == "slash"
    assert state.settings["tienoteheads"] == "show"


def test_cmd_set_tabnotation_full_reapply_overrides_user_toggles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "tabnotation=full", str(tmp_path / "cfg.toml"))
    assert state.settings["showdur"] == "on"
    assert state.settings["timesigstyle"] == "fraction"
    # User override after preset should stick until preset is reapplied.
    cmd.cmd_set(state, "showdur=off timesigstyle=numeric tiecuestyle=hide", str(tmp_path / "cfg.toml"))
    assert state.settings["showdur"] == "off"
    assert state.settings["timesigstyle"] == "numeric"
    assert state.settings["tiecuestyle"] == "hide"
    cmd.cmd_set(state, "tabnotation=full", str(tmp_path / "cfg.toml"))
    assert state.settings["showdur"] == "on"
    assert state.settings["timesigstyle"] == "fraction"
    assert state.settings["tiecuestyle"] == "paren"


def test_cmd_set_tie_notehead_policy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "tienoteheads=hide", str(tmp_path / "cfg.toml"))
    assert state.settings["tienoteheads"] == "hide"
    cmd.cmd_set(state, "tienoteheads=parenthesize", str(tmp_path / "cfg.toml"))
    assert state.settings["tienoteheads"] == "parenthesize"
    cmd.cmd_set(state, "glisscuestyle=paren", str(tmp_path / "cfg.toml"))
    assert state.settings["glisscuestyle"] == "paren"


def test_cmd_set_ft3_extra_display_policies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(
        state,
        "showspans=on showfingerings=off showornaments=on ft3fingering=right ft3ornaments=left",
        str(tmp_path / "cfg.toml"),
    )
    assert state.settings["showspans"] == "on"
    assert state.settings["showextras"] == "on"  # mirrored compatibility key
    assert state.settings["showfingerings"] == "off"
    assert state.settings["showornaments"] == "on"
    assert state.settings["showft3extras"] == "off"  # bundle mirror follows both_on rule
    assert state.settings["ft3fingering"] == "right"
    assert state.settings["ft3ornaments"] == "left"


def test_cmd_set_deprecated_show_aliases_map_to_explicit_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "showextras=on showft3extras=off", str(tmp_path / "cfg.toml"))
    assert state.settings["showspans"] == "on"
    assert state.settings["showextras"] == "on"
    assert state.settings["showfingerings"] == "off"
    assert state.settings["showornaments"] == "off"
    assert state.settings["showft3extras"] == "off"


def test_cmd_set_meta_presets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(
            note_type=4,
            dotted=False,
            grid=None,
            notes=[Note(4, 2, 0), Note(3, 2, 0), Note(1, 0, 0)],
        ),
    ]

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "guitar", str(tmp_path / "cfg.toml"))
    assert state.settings["style"] == "italian"
    assert state.settings["tuning"] == "e2a2d3g3b3e4"
    assert state.settings["strings"] == "6"
    assert state.settings["italianorient"] == "reverse"
    notes_after_guitar = {(n.string, n.fret) for n in state.piece.bars[0].chords[0].notes}
    assert (4, 1) in notes_after_guitar
    assert (3, 2) in notes_after_guitar
    assert "partial convert" in state.message
    cmd.cmd_set(state, "guitar", str(tmp_path / "cfg.toml"))
    notes_after_repeat = {(n.string, n.fret) for n in state.piece.bars[0].chords[0].notes}
    assert (4, 1) in notes_after_repeat
    assert "partial convert" not in state.message
    cmd.cmd_set(state, "lute", str(tmp_path / "cfg.toml"))
    assert state.settings["style"] == "french"
    assert state.settings["tuning"] == "g2c3f3a3d4g4"
    assert state.settings["strings"] == "6"
    notes_after_lute = {(n.string, n.fret) for n in state.piece.bars[0].chords[0].notes}
    assert (3, 3) in notes_after_lute
    assert "partial convert" in state.message


def test_cmd_set_guitar_partial_convert_moves_open_bridge_course_to_next_course(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(
            note_type=4,
            dotted=False,
            grid=None,
            notes=[Note(4, 0, 0)],
        ),
    ]

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "guitar", str(tmp_path / "cfg.toml"))
    notes = state.piece.bars[0].chords[0].notes
    assert len(notes) == 1
    # Temporary bridge keeps pitch by moving to the next course if -1 would go negative.
    assert notes[0].string == 5
    assert notes[0].fret >= 0
    assert "partial convert" in state.message


def test_cmd_set_guitar_partial_convert_negative_shift_uses_target_tuning_for_next_course(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(
            note_type=4,
            dotted=False,
            grid=None,
            notes=[Note(4, 0, 0)],
        ),
    ]

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "guitar", str(tmp_path / "cfg.toml"))
    note = state.piece.bars[0].chords[0].notes[0]
    # Equivalent pitch under target guitar tuning lands on the next course with
    # a target-tuning fret (old source-tuning math produced a different fret).
    assert (note.string, note.fret) == (5, 7)


def test_cmd_set_guitar_partial_convert_drops_open_bridge_course_if_next_course_occupied(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(
            note_type=4,
            dotted=False,
            grid=None,
            notes=[Note(4, 0, 0), Note(5, 2, 0)],
        ),
    ]

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "guitar", str(tmp_path / "cfg.toml"))
    notes = state.piece.bars[0].chords[0].notes
    assert all(n.string != 4 for n in notes)
    assert any(n.string == 5 for n in notes)
    # The original next-course note remains; the negative-shift open note is dropped.
    assert len(notes) == 1
    assert "partial convert" in state.message


def test_cmd_set_guitar_rescues_removed_bass_course_one_octave_up(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    state = _state()
    state.piece.strings = 7
    state.settings["strings"] = "7"
    state.settings["tuning"] = "f2g2c3f3a3d4g4"
    state.piece.bars[0].chords = [
        Chord(
            note_type=4,
            dotted=False,
            grid=None,
            notes=[Note(7, 0, 0)],
        ),
    ]

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "guitar", str(tmp_path / "cfg.toml"))
    notes = state.piece.bars[0].chords[0].notes
    assert state.piece.strings == 6
    assert len(notes) == 1
    # 7th-course f2 is rescued as f3 on the target 6-string guitar layout.
    assert (notes[0].string, notes[0].fret) == (4, 3)


def test_cmd_set_bool_shortcuts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "showdur", str(tmp_path / "cfg.toml"))
    assert state.settings["showdur"] == "on"
    cmd.cmd_set(state, "noshowdur", str(tmp_path / "cfg.toml"))
    assert state.settings["showdur"] == "off"


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
    content_after = out_txt.read_text(encoding="utf-8")
    assert content_after == render_ascii_snapshot(state)
    lines = content_after.splitlines()
    assert len(lines) == state.screen_height


def test_cmd_set_tuning_baroque_alias(tmp_path: Path) -> None:
    state = _state()
    cfg = str(tmp_path / "cfg.toml")
    cmd.cmd_set(state, "tuning=baroque13", cfg)
    assert state.settings["tuning"] == "a4b-4c4d4e4f4g4a3d3f3a2d2f2"


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

    def _export_musicxml(_path: str, *_args: object, **_kwargs: object) -> str:
        return "Xml ok"

    def _export_mxl(_path: str, *_args: object, **_kwargs: object) -> str:
        return "Mxl ok"

    pdf_called: dict[str, str] = {}

    def _print_pdf(_path: str) -> str:
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
    monkeypatch.setattr("oud.editor.midi_control.start_midi", _start_midi)

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
        "Repeat must be none/start/end/dots/both/dc/ds/fine/coda/"
        "tocoda/dcalfine/dcalcoda/dsalfine/dsalcoda"
    )
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


def test_apply_command_dispatch_executes_all_registered_specs(
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
        "cmd_info",
        "cmd_plugins",
        "cmd_bar",
        "cmd_chord",
        "cmd_stave",
        "cmd_slur",
        "cmd_tie",
        "cmd_hold",
        "cmd_barline",
        "cmd_repeat",
        "cmd_dynamic",
        "cmd_fermata",
        "cmd_time",
        "cmd_verify",
    }
    patched_3arg = {
        "cmd_set",
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
        "plugins": "",
        "bar": "add",
        "chord": "insert",
        "stave": "break",
        "slur": "0 0 0",
        "tie": "0 0 0",
        "hold": "0 0 0",
        "barline": "thin",
        "repeat": "start",
        "dynamic": "mf",
        "fermata": "on",
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
