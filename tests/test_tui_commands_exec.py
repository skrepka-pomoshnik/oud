import copy
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest

from oud.editor.commands import dispatch as cmd_ops
from oud.editor.core.state import EditorState
from oud.editor.editing.primitives.tablature import french_to_fret
from oud.editor.services.io.files import render_ascii_snapshot
from oud.importers.tab import TabData
from oud.presentation.tui import commands as cmd
from oud.settings import load_settings
from petrucci.core.model import Bar, Chord, LyricEvent, MelodyEvent, Note, Piece
from petrucci.core.music.tuning import parse_tuning_pitches


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


def test_apply_command_dark_light_set_theme(tmp_path: Path) -> None:
    state = _state()
    cfg = str(tmp_path / "cfg.toml")
    cmd.apply_command(state, "dark", cfg)
    assert state.settings["theme"] == "dark"
    cmd.apply_command(state, "light", cfg)
    assert state.settings["theme"] == "light"
    cmd.apply_command(state, "set theme=auto", cfg)
    assert state.settings["theme"] == "auto"
    cmd.apply_command(state, "set theme=neon", cfg)
    assert state.settings["theme"] == "auto"
    assert "Theme must be" in state.message


def test_apply_command_help_pipes_through_less(tmp_path: Path, monkeypatch) -> None:
    state = _state()
    calls: list[object] = []
    state.suspend_tui = lambda: calls.append("suspend")
    state.resume_tui = lambda: calls.append("resume")
    monkeypatch.setattr(subprocess, "run", lambda argv, **_kwargs: calls.append(argv[0]))
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    cmd.apply_command(state, "help", str(tmp_path / "cfg.toml"))
    assert calls == ["suspend", "/usr/bin/less", "resume"]
    assert state.message == ""


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
        "strings=7 style=italian showdur=on frenchc=alt",
        str(tmp_path / "cfg.toml"),
    )
    assert state.settings["strings"] == "7"
    assert state.settings["style"] == "italian"
    assert state.settings["showdur"] == "on"
    assert state.settings["frenchc"] == "alt"
    # Document properties stay in the session; only preferences persist.
    assert saved == {"showdur": "on", "frenchc": "alt"}
    state.overrides[(0, 0, 0)] = "0"
    cmd.cmd_convert(state, "french", str(tmp_path / "cfg.toml"))
    assert state.settings["style"] == "french"


def test_cmd_transpose_retune_and_courseshift_with_undo(tmp_path: Path) -> None:
    state = _state(bars=1)
    state.piece.bars[0].chords = [
        Chord(
            note_type=4,
            dotted=False,
            grid=None,
            notes=[Note(1, 0, 0), Note(3, 2, 0)],
        ),
    ]
    state.cursor_bar = 0
    state.cursor_col = 0
    state.cursor_string = 0
    cmd.apply_command(state, "transpose 2", str(tmp_path / "cfg.toml"))
    assert state.undo_stack[-1].kind == "group"
    assert state.undo_stack[-1].data["label"] == "transpose 2"
    notes = {(n.string, n.fret) for n in state.piece.bars[0].chords[0].notes}
    assert notes != {(1, 0), (3, 2)}
    assert "Transposed +2" in state.message
    cmd.apply_command(state, "undo", str(tmp_path / "cfg.toml"))
    notes = {(n.string, n.fret) for n in state.piece.bars[0].chords[0].notes}
    assert notes == {(1, 0), (3, 2)}

    cmd.apply_command(state, "retune e2a2d3g3b3e4", str(tmp_path / "cfg.toml"))
    assert state.undo_stack[-1].kind == "group"
    assert state.undo_stack[-1].data["label"] == "retune e2a2d3g3b3e4"
    assert sorted(parse_tuning_pitches(state.settings["tuning"])) == sorted(
        parse_tuning_pitches("e2a2d3g3b3e4"),
    )
    assert state.settings["strings"] == "6"
    assert "Retuned:" in state.message
    cmd.apply_command(state, "undo", str(tmp_path / "cfg.toml"))
    assert state.settings["tuning"] == "g2c3f3a3d4g4"

    # Shift cursor note (top string) down one course while preserving pitch.
    cmd.apply_command(state, "courseshift down", str(tmp_path / "cfg.toml"))
    shifted = state.piece.bars[0].chords[0].notes
    assert any(n.string == 2 for n in shifted)
    assert "Course shift down" in state.message


def test_cmd_courseshift_works_on_grid_overrides_and_keeps_pitch(tmp_path: Path) -> None:
    state = _state(bars=1)
    state.cursor_bar = 0
    state.cursor_col = 0
    state.cursor_string = 0
    state.overrides[(0, 0, 0)] = "c"  # fret 2 on cursor string
    state.durations[(0, 0, 0)] = 4
    source_tuning = parse_tuning_pitches(state.settings["tuning"])
    src_pitch = source_tuning[0] + 2

    cmd.apply_command(state, "courseshift down", str(tmp_path / "cfg.toml"))

    moved = [(k, v) for (k, v) in state.overrides.items() if k[0] == 0 and k[2] == 0]
    assert len(moved) == 1
    (bar, s_idx, col), glyph = moved[0]
    assert (bar, col) == (0, 0)
    assert s_idx == 1
    fret = french_to_fret(glyph)
    assert fret is not None
    dst_pitch = source_tuning[s_idx] + fret
    assert dst_pitch == src_pitch
    assert "Course shift down" in state.message


def test_cmd_transpose_and_retune_preserve_grid_override_pitch_rules(tmp_path: Path) -> None:
    state = _state(bars=1)
    state.overrides[(0, 0, 0)] = "b"  # fret 1
    state.durations[(0, 0, 0)] = 4
    state.cursor_bar = 0
    state.cursor_col = 0
    state.cursor_string = 0
    src_tuning = parse_tuning_pitches(state.settings["tuning"])
    src_pitch = src_tuning[0] + 1

    cmd.apply_command(state, "transpose 2", str(tmp_path / "cfg.toml"))
    trans_key, trans_glyph = next(iter(state.overrides.items()))
    trans_fret = french_to_fret(trans_glyph)
    assert trans_fret is not None
    trans_tuning = parse_tuning_pitches(state.settings["tuning"])
    trans_pitch = trans_tuning[trans_key[1]] + trans_fret
    assert trans_pitch == src_pitch + 2
    assert "Transposed +2" in state.message

    cmd.apply_command(state, "retune e2a2d3g3b3e4", str(tmp_path / "cfg.toml"))
    ret_key, ret_glyph = next(iter(state.overrides.items()))
    ret_fret = french_to_fret(ret_glyph)
    assert ret_fret is not None
    ret_tuning = parse_tuning_pitches(state.settings["tuning"])
    ret_pitch = ret_tuning[ret_key[1]] + ret_fret
    assert ret_pitch == trans_pitch
    assert "Retuned:" in state.message


def test_cmd_pause_cursor_and_col_commands(tmp_path: Path) -> None:
    state = _state(bars=3)
    cmd.apply_command(state, "pause", str(tmp_path / "cfg.toml"))
    assert state.message == "MIDI not playing"

    quarter = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[1].chords = [copy.deepcopy(quarter) for _ in range(3)]
    cmd.apply_command(state, "cursor 2 3 5", str(tmp_path / "cfg.toml"))
    assert state.cursor_bar == 1
    assert state.cursor_string == 2
    assert state.cursor_onset == Fraction(3, 4)
    assert state.message == "Cursor 2:3:4"

    cmd.apply_command(state, "col 2", str(tmp_path / "cfg.toml"))
    assert state.cursor_onset == Fraction(1, 4)
    assert state.message == "Event 2"

    cmd.apply_command(state, "cursor nope", str(tmp_path / "cfg.toml"))
    assert state.message.startswith("Usage: cursor")


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
        "soundfont=sf2 tempo=120 showextras=on showtactus=on italianorient=reverse "
        "maxrepeats=30 scrollmode=page beatsnap=soft timesigstyle=fraction flaglean=left "
        "multifretspacing=separated fretlabelmode=letters "
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
    assert state.settings["showextras"] == "on"
    assert state.settings["showtactus"] == "on"
    assert state.settings["italianorient"] == "reverse"
    assert state.settings["maxrepeats"] == "30"
    assert state.settings["scrollmode"] == "page"
    assert state.settings["beatsnap"] == "soft"
    assert state.settings["timesigstyle"] == "fraction"
    assert state.settings["flaglean"] == "left"
    assert state.settings["multifretspacing"] == "separated"
    assert state.settings["fretlabelmode"] == "letters"
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


def test_cmd_set_movementmode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "movementmode=note", str(tmp_path / "cfg.toml"))
    assert state.settings["movementmode"] == "note"


def test_cmd_set_tabnotation_full_preset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "tabnotation=full", str(tmp_path / "cfg.toml"))
    assert state.settings["tabnotation"] == "full"
    assert state.settings["showdur"] == "on"
    assert state.settings["showextras"] == "on"
    assert state.settings["showtuplets"] == "on"
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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "showextras=on showft3extras=off", str(tmp_path / "cfg.toml"))
    assert state.settings["showspans"] == "on"
    assert state.settings["showextras"] == "on"


def test_sign_commands_arpeggio_separee_and_tuplet() -> None:
    state = _state()
    quarter = Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])
    state.piece.bars[0].chords = [copy.deepcopy(quarter) for _ in range(4)]
    state.cursor_bar = 0
    state.cursor_onset = Fraction(3, 4)
    key = (0, state.cursor_col)
    assert key[1] > 0

    cmd.apply_command(state, "arpeggio on", "cfg.toml")
    assert state.ornaments[key] == "~"
    assert state.message == "Arpeggio on"

    cmd.apply_command(state, "separee on", "cfg.toml")
    assert state.ornaments[key] == ":"
    assert state.message == "Separee on"

    cmd.apply_command(state, "tuplet 3", "cfg.toml")
    assert state.annotations[key] == "³"
    assert state.message == "Tuplet 3"

    cmd.apply_command(state, "tuplet clear", "cfg.toml")
    assert key not in state.annotations
    assert state.message == "Tuplet cleared"


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
    src_tuning = parse_tuning_pitches(state.settings["tuning"])
    before_pitches = sorted(src_tuning[n.string - 1] + n.fret for n in state.piece.bars[0].chords[0].notes)
    cmd.cmd_set(state, "guitar", str(tmp_path / "cfg.toml"))
    assert state.settings["style"] == "italian"
    assert state.settings["tuning"] == "e2a2d3g3b3e4"
    assert state.settings["strings"] == "6"
    assert state.settings["italianorient"] == "reverse"
    notes_after_guitar = {(n.string, n.fret) for n in state.piece.bars[0].chords[0].notes}
    assert len(notes_after_guitar) == 3
    guitar_tuning = parse_tuning_pitches(state.settings["tuning"])
    after_guitar_pitches = sorted(guitar_tuning[n.string - 1] + n.fret for n in state.piece.bars[0].chords[0].notes)
    assert after_guitar_pitches == before_pitches
    assert "converted content" in state.message
    cmd.cmd_set(state, "guitar", str(tmp_path / "cfg.toml"))
    notes_after_repeat = {(n.string, n.fret) for n in state.piece.bars[0].chords[0].notes}
    assert notes_after_repeat == notes_after_guitar
    assert "converted content" not in state.message
    cmd.cmd_set(state, "lute", str(tmp_path / "cfg.toml"))
    assert state.settings["style"] == "french"
    assert state.settings["tuning"] == "g2c3f3a3d4g4"
    assert state.settings["strings"] == "6"
    lute_tuning = parse_tuning_pitches(state.settings["tuning"])
    after_lute_pitches = sorted(lute_tuning[n.string - 1] + n.fret for n in state.piece.bars[0].chords[0].notes)
    assert after_lute_pitches == before_pitches
    assert "converted content" in state.message


def test_cmd_set_guitar_preset_retunes_content_preserving_pitch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
    source_pitch = parse_tuning_pitches(state.settings["tuning"])[3]  # course 4 open
    cmd.cmd_set(state, "guitar", str(tmp_path / "cfg.toml"))
    notes = state.piece.bars[0].chords[0].notes
    assert len(notes) == 1
    target_tuning = parse_tuning_pitches(state.settings["tuning"])
    assert target_tuning[notes[0].string - 1] + notes[0].fret == source_pitch
    assert "converted content" in state.message


def test_cmd_set_guitar_preset_retune_uses_target_tuning_mapping(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
    assert (note.string, note.fret) == (4, 3)


def test_cmd_set_guitar_preset_retune_preserves_chord_without_string_collisions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
    src_tuning = parse_tuning_pitches(state.settings["tuning"])
    before_pitches = sorted(src_tuning[n.string - 1] + n.fret for n in state.piece.bars[0].chords[0].notes)
    cmd.cmd_set(state, "guitar", str(tmp_path / "cfg.toml"))
    notes = state.piece.bars[0].chords[0].notes
    assert len({n.string for n in notes}) == len(notes)
    tgt_tuning = parse_tuning_pitches(state.settings["tuning"])
    after_pitches = sorted(tgt_tuning[n.string - 1] + n.fret for n in notes)
    assert after_pitches == before_pitches
    assert "converted content" in state.message


def test_cmd_set_guitar_reassigns_removed_bass_course_under_target_tuning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
    src_tuning = parse_tuning_pitches(state.settings["tuning"])
    before_pitch = src_tuning[6]
    cmd.cmd_set(state, "guitar", str(tmp_path / "cfg.toml"))
    notes = state.piece.bars[0].chords[0].notes
    assert state.piece.strings == 6
    assert len(notes) == 1
    tgt_tuning = parse_tuning_pitches(state.settings["tuning"])
    assert tgt_tuning[notes[0].string - 1] + notes[0].fret == before_pitch


def test_cmd_set_bool_shortcuts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state = _state()

    def _save(_path: str, _settings: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(cmd_ops, "save_settings", _save)
    cmd.cmd_set(state, "showdur", str(tmp_path / "cfg.toml"))
    assert state.settings["showdur"] == "on"
    cmd.cmd_set(state, "noshowdur", str(tmp_path / "cfg.toml"))
    assert state.settings["showdur"] == "off"
    cmd.cmd_set(state, "playbackscroll=off", str(tmp_path / "cfg.toml"))
    assert state.settings["playbackscroll"] == "off"
    cmd.cmd_set(state, "playbackscroll=on", str(tmp_path / "cfg.toml"))
    assert state.settings["playbackscroll"] == "on"


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
    monkeypatch.setattr("oud.editor.commands.dispatch.load_tab_data", lambda _path: tab_data)
    cmd.cmd_open(state, str(tmp_path / "file.tab"))
    assert state.piece.title == "Tab"
    assert state.bar_width == 8
    monkeypatch.setattr("oud.editor.commands.dispatch.load_tab_data", lambda _path: None)
    monkeypatch.setattr("oud.editor.commands.dispatch.load_tab", lambda _path: tab_piece)
    cmd.cmd_open(state, str(tmp_path / "other.tab"))
    assert state.piece.title == "Tab"
    ft3_piece = Piece(title="Ft3", bars=[Bar()], strings=6)
    monkeypatch.setattr("oud.editor.commands.dispatch.load_ft3", lambda _path: ft3_piece)
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
    assert state.settings["tuning"] == "a1b-1c2d2e2f2g2a2d3f3a3d4f4"


def test_cmd_bar_and_chord() -> None:
    state = _state()
    cmd.cmd_bar(state, "add")
    assert len(state.piece.bars) == 3
    cmd.cmd_bar(state, "del")
    assert len(state.piece.bars) == 2
    state = _state(bars=4)
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(1, 0, 1)] = "b"
    cmd.cmd_bar(state, "yank 2")
    assert state.message == "Bars yanked: 2"
    cmd.cmd_bar(state, "paste 2")
    assert len(state.piece.bars) == 8
    assert state.message == "Bars pasted: 4"
    cmd.cmd_bar(state, "del 3")
    assert len(state.piece.bars) == 5
    assert state.message == "Bars deleted: 3"
    cmd.cmd_chord(state, "insert 3")
    assert len(state.piece.bars[state.cursor_bar].chords) == 3
    assert state.message == "Chords added: 3"
    state.cursor_col = 0
    cmd.cmd_chord(state, "yank 2")
    assert state.yanked_chords is not None
    assert len(state.yanked_chords) == 2
    assert state.message == "Chords yanked: 2"
    state.cursor_col = state.bar_width - 1
    cmd.cmd_chord(state, "paste")
    assert len(state.piece.bars[state.cursor_bar].chords) == 5
    assert state.message == "Chords pasted: 2"
    state.cursor_col = 0
    cmd.cmd_chord(state, "delete 2")
    assert len(state.piece.bars[state.cursor_bar].chords) == 3
    assert state.message == "Chords deleted: 2"
    cmd.cmd_chord(state, "delete")
    assert len(state.piece.bars[state.cursor_bar].chords) == 2
    state.cursor_col = 0
    cmd.cmd_chord(state, "delete 2")
    assert state.piece.bars[state.cursor_bar].chords == []
    state.yanked_chords = None
    cmd.cmd_chord(state, "paste")
    assert state.message == "No yanked chords"
    cmd.cmd_chord(state, "other")
    assert state.message == "Chord action: add/del/yank/paste [count]"
    cmd.cmd_bar(state, "other")
    assert state.message == "Bar action: add/after/before/insert/del/yank/paste [count]"


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
    state.piece.bars[0].chords = [Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]) for _ in range(4)]
    state.settings["time"] = "4/4"
    cmd.cmd_verify(state, "")
    assert state.message == "Measure ok"
    state.piece.bars[0].chords = [Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]
    cmd.cmd_verify(state, "")
    assert state.message.startswith("Underfull")
    cmd.cmd_verify(state, "render")
    assert state.message in ("Render ok", "Render map collapsed to one column")
    cmd.cmd_verify(state, "other")
    assert state.message == "Verify modes: bar|render"


def test_cmd_vocal_clear_removes_melody_and_lyrics_from_piece() -> None:
    state = _state()
    state.piece = Piece(
        title="Vocal",
        bars=[
            Bar(
                melody_grid="3 8 a",
                lyrics=["Can she"],
                melody_events=[MelodyEvent("3", 0)],
                lyric_event_rows=[[LyricEvent("Can", 0)]],
            ),
            Bar(),
        ],
        strings=6,
    )
    cmd.cmd_vocal(state, "clear")
    assert state.modified is True
    assert "Cleared vocal layer in 1 bar" in state.message
    assert state.piece.bars[0].melody_grid is None
    assert state.piece.bars[0].melody_events == []
    assert state.piece.bars[0].lyrics == []
    assert state.piece.bars[0].lyric_event_rows == []


def test_the_obsolete_grid_setting_is_gone(tmp_path: Path) -> None:
    config = tmp_path / "cfg.toml"
    config.write_text('[settings]\ngrid = "on"\nshowdur = "on"\n', encoding="utf-8")

    settings = load_settings(str(config))

    assert "grid" not in settings
    assert settings["showdur"] == "on"
    state = _state()
    cmd.cmd_set(state, "grid=on", str(config))
    assert state.message == "Unknown set key: grid"
