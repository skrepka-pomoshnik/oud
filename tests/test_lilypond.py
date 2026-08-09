import subprocess
from pathlib import Path

from oud.exports import _lilypond_document as lp
from oud.exports.lilypond import export_lilypond
from petrucci.model import (
    Bar,
    Chord,
    Note,
    Piece,
)


def test_export_lilypond_writes_tabstaff(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "out.ly"
    msg = export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "time": "4/4", "key": "C"},
    )
    assert "Wrote" in msg
    text = path.read_text(encoding="utf-8")
    assert "\\new TabStaff" in text
    assert "stringTunings" in text
    assert "\\time 4/4" in text
    assert "\\tabFullNotation" not in text
    assert "\\override Clef.stencil = ##f" in text
    assert "\\override ClefModifier.stencil = ##f" in text


def test_export_lilypond_emits_source_pitches_without_exhaustive_tab_assignment(tmp_path, monkeypatch) -> None:
    def fail_assignment(*_args, **_kwargs):
        raise AssertionError

    monkeypatch.setattr(lp, "assign_chord_pitches", fail_assignment, raising=False)
    notes = [Note(string, fret, 0) for string, fret in enumerate((0, 2, 4, 5, 7, 9), start=1)]
    piece = Piece(
        title="Dense chord",
        bars=[Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=notes)])],
        strings=6,
        tuning="g2c3f3a3d4g4",
    )
    path = tmp_path / "dense.ly"

    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4"},
    )

    assert "<" in path.read_text(encoding="utf-8")


def test_export_lilypond_tabnotation_full_emits_tab_full_notation(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "full.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "tabnotation": "full"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\tabFullNotation" in text
    assert r"\set fingeringOrientations = #'(left)" in text
    assert r"\set strokeFingerOrientations = #'(right)" in text


def test_export_lilypond_extends_6_course_tuning_for_8_course_piece_in_low_to_high_order(
    tmp_path,
) -> None:
    bar = Bar(
        chords=[
            Chord(
                note_type=4,
                dotted=False,
                grid=None,
                notes=[Note(1, 0, 0), Note(8, 0, 0)],
            ),
        ],
    )
    piece = Piece(title="T", bars=[bar], strings=8)
    path = tmp_path / "eight.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4"},
    )
    text = path.read_text(encoding="utf-8")
    assert r"stringTunings = \stringTuning <e, f, g, c f a d' g'>" in text
    # Regression: extra-course note must not be silently dropped from the exported chord.
    assert "<" in text and ">" in text
    chord_line = next(line for line in text.splitlines() if line.strip().startswith("<"))
    assert chord_line.count(" ") >= 2  # at least two pitch tokens + duration suffix


def test_export_lilypond_uses_source_tuning_pitch_fallback_when_target_tuning_differs(tmp_path) -> None:
    bar = Bar(
        chords=[
            Chord(
                note_type=4,
                dotted=False,
                grid=None,
                notes=[Note(7, 12, 0)],  # out of 6-course main range, but pitch is assignable
            ),
        ],
    )
    piece = Piece(title="T", bars=[bar], strings=7, tuning="g2c3f3a3d4g4d2")
    path = tmp_path / "fallback.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4"},  # shorter target tuning; exporter extends for TabStaff
    )
    text = path.read_text(encoding="utf-8")
    # Regression: do not emit a rest just because source note is on an extra course.
    assert "  r4" not in text
    note_line = next(
        line
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith(("\\", "%", "{")) and "4" in line
    )
    assert "r4" not in note_line


def test_export_lilypond_petrucci_notehead_style_setting(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "petrucci.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g4d4a3f3c3g2",
            "tabnotation": "full",
            "lynoteheads": "petrucci",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "\\tabFullNotation" in text
    assert "\\override NoteHead.style = #'petrucci" in text

    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g4d4a3f3c3g2",
            "tabnotation": "full",
            "lynoteheads": "classic",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "\\override NoteHead.style = #'petrucci" not in text


def test_export_lilypond_barline_and_repeat(tmp_path) -> None:
    bar1 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    bar1.repeat = ".:"
    bar2 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    bar2.barline = "||"
    piece = Piece(title="T", bars=[bar1, bar2], strings=6)
    path = tmp_path / "out.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2"},
    )
    text = path.read_text(encoding="utf-8")
    assert '\\bar ".|:"' in text
    assert '\\bar "||"' in text


def test_export_lilypond_repeat_cue_marks(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    bar.repeat = "DC al Fine"
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "cue.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2"},
    )
    text = path.read_text(encoding="utf-8")
    assert "D.C. al Fine" in text


def test_export_lilypond_bar_dynamic_and_fermata_marks(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    bar.dynamic = "mf"
    bar.fermata = True
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "signs.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2"},
    )
    text = path.read_text(encoding="utf-8")
    assert '\\mark \\markup { "mf" }' in text
    assert "scripts.ufermata" in text


def test_export_lilypond_ft3_extras_markups_only_in_full_tabnotation(tmp_path) -> None:
    bar = Bar(
        chords=[
            Chord(
                note_type=4,
                dotted=False,
                grid=None,
                notes=[
                    Note(
                        1,
                        1,
                        0,
                        left_fingering="4",
                        right_fingering="thumb",
                        left_ornament="#",
                        arpeggio="single",
                    ),
                ],
            ),
        ],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "extras.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "tabnotation": "minimal"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\tiny" not in text

    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g4d4a3f3c3g2",
            "tabnotation": "full",
            "showfingerings": "on",
            "showornaments": "on",
            "ft3fingering": "both",
            "ft3ornaments": "left",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "\\tiny" in text
    assert '"#"' in text
    assert "-4" in text
    assert r'\rightHandFinger \markup { "t" }' in text
    assert r"\arpeggio" in text


def test_export_lilypond_uses_native_fingering_attachments_for_numeric_ft3_fingerings(
    tmp_path,
) -> None:
    bar = Bar(
        chords=[
            Chord(
                note_type=4,
                dotted=False,
                grid=None,
                notes=[Note(1, 2, 0, left_fingering="4", right_fingering="2")],
            ),
        ],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "native_finger.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g4d4a3f3c3g2",
            "tabnotation": "full",
            "showfingerings": "on",
            "showornaments": "off",
            "ft3fingering": "both",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "-4" in text
    assert r"\rightHandFinger #2" in text
    assert "\\tiny" not in text


def test_export_lilypond_uses_native_thumb_pluck_attachment_for_ft3_thumb(tmp_path) -> None:
    bar = Bar(
        chords=[
            Chord(
                note_type=4,
                dotted=False,
                grid=None,
                notes=[Note(1, 1, 0, right_fingering="thumb")],
            ),
        ],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "native_thumb.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g4d4a3f3c3g2",
            "tabnotation": "full",
            "showfingerings": "on",
            "showornaments": "off",
            "ft3fingering": "right",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert r'\rightHandFinger \markup { "t" }' in text
    assert r'_\markup { \tiny "t" }' not in text
    assert r'^\markup { \tiny "t" }' not in text


def test_export_lilypond_ft3_extras_collects_multiple_notes_and_suppresses_open_lh_digits(
    tmp_path,
) -> None:
    bar = Bar(
        chords=[
            Chord(
                note_type=4,
                dotted=False,
                grid=None,
                notes=[
                    Note(1, 0, 0, left_fingering="1", right_fingering="thumb", left_ornament="#"),
                    Note(2, 2, 0, left_fingering="4", right_fingering="2", left_ornament="dot-left"),
                    Note(3, 3, 0, left_fingering="4", right_fingering="2", left_ornament="dot-left"),
                ],
            ),
        ],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "extras_multi.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g4d4a3f3c3g2",
            "tabnotation": "full",
            "showfingerings": "on",
            "showornaments": "on",
            "ft3fingering": "both",
            "ft3ornaments": "left",
        },
    )
    text = path.read_text(encoding="utf-8")
    # Open-string LH "1" is suppressed; chord-level export aggregates/dedups remaining cues.
    assert '"1"' not in text
    assert "-4\\rightHandFinger #2" in text or "-4 \\rightHandFinger #2" in text
    assert '"# ."' in text or '". #"' in text
    # Thumb stays as fallback markup; numeric RH fingering is exported natively.
    assert '"t"' in text


def test_export_lilypond_ft3_barre_semantics_emit_named_markup(tmp_path) -> None:
    bar = Bar(
        chords=[
            Chord(
                note_type=4,
                dotted=False,
                grid=None,
                notes=[Note(1, 2, 0, barre=True)],
            ),
        ],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "barre.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g4d4a3f3c3g2",
            "tabnotation": "full",
            "showfingerings": "on",
            "showornaments": "off",
            "ft3fingering": "left",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert '"barre"' in text


def test_export_lilypond_repeat_both_and_ds_coda(tmp_path) -> None:
    bar1 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    bar1.repeat = ":|:"
    bar2 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    bar2.repeat = "DS al Coda"
    piece = Piece(title="T", bars=[bar1, bar2], strings=6)
    path = tmp_path / "repeat_variants.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2"},
    )
    text = path.read_text(encoding="utf-8")
    assert '\\bar ":|:"' in text
    assert "D.S. al Coda" in text


def test_export_lilypond_slur_tie_hold(tmp_path) -> None:
    bar = Bar()
    piece = Piece(title="T", bars=[bar], strings=6)
    overrides = {(0, 0, 0): "a", (0, 0, 2): "b"}
    durations = {(0, 0, 0): 4, (0, 0, 2): 4}
    slurs = [(0, 0, 2)]
    ties = [(0, 2, 2)]
    holds = [(0, 0, 0)]
    path = tmp_path / "out.ly"
    export_lilypond(
        str(path),
        piece,
        overrides=overrides,
        durations=durations,
        bar_width=4,
        settings={"tuning": "g4d4a3f3c3g2"},
        slurs=slurs,
        ties=ties,
        holds=holds,
    )
    text = path.read_text(encoding="utf-8")
    assert "(" in text
    assert ")" in text
    assert "~" in text
    assert "\\laissezVibrer" in text


def test_print_lilypond_pdf_handles_non_utf8_stderr(monkeypatch) -> None:
    monkeypatch.setattr(lp.shutil, "which", lambda _name: "/usr/bin/lilypond")

    def _run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            1,
            ["lilypond", "x.ly"],
            stderr=b"warning...\nboom:\x8b\xff\n",
        )

    monkeypatch.setattr(lp.subprocess, "run", _run)
    msg = lp.print_lilypond_pdf("x.ly")
    assert msg.startswith("LilyPond failed:")
    assert "boom:" in msg


def test_print_lilypond_pdf_reports_missing_pdf_after_success(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(lp.shutil, "which", lambda _name: "/usr/bin/lilypond")

    def _run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["lilypond", "x.ly"], 0)

    monkeypatch.setattr(lp.subprocess, "run", _run)
    ly_path = tmp_path / "x.ly"
    ly_path.write_text("%", encoding="utf-8")
    msg = lp.print_lilypond_pdf(str(ly_path))
    assert msg.startswith("LilyPond finished but PDF not found:")


def test_print_lilypond_pdf_uses_configured_binary(monkeypatch) -> None:
    requested: list[str] = []

    def _which(name: str) -> None:
        requested.append(name)

    monkeypatch.setattr(lp.shutil, "which", _which)
    msg = lp.print_lilypond_pdf("x.ly", binary="/opt/lilypond-2.24/bin/lilypond")

    assert requested == ["/opt/lilypond-2.24/bin/lilypond"]
    assert msg == "LilyPond binary not found: /opt/lilypond-2.24/bin/lilypond"


def test_print_lilypond_pdf_runs_in_output_dir_and_finds_pdf(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(lp.shutil, "which", lambda _name: "/usr/bin/lilypond")
    calls: dict[str, object] = {}

    def _run(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["cwd"] = kwargs.get("cwd")
        cwd = Path(kwargs["cwd"])
        out_stem = cmd[2]
        (cwd / f"{out_stem}.pdf").write_bytes(b"%PDF-1.4\n")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(lp.subprocess, "run", _run)
    out_dir = tmp_path / "nested"
    out_dir.mkdir()
    ly_path = out_dir / "score.ly"
    ly_path.write_text("%", encoding="utf-8")
    msg = lp.print_lilypond_pdf(str(ly_path), str(out_dir / "score"))
    assert calls["cwd"] == out_dir.resolve()
    assert msg == f"Printed {(out_dir / 'score.pdf').resolve()}"


def test_export_lilypond_parses_ft3_style_key_major_minor_tokens(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "keys.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "key": "GM"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\key g \\major" in text

    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "key": "Dm"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\key d \\minor" in text


def test_export_lilypond_parses_spaced_key_names_and_skips_invalid_key(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "keys2.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "key": "Bb major"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\key bes \\major" in text

    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "key": "GM?"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\key " not in text


def test_export_lilypond_uses_piece_key_when_settings_key_missing(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    piece = Piece(title="T", bars=[bar], strings=6, key="GM")
    path = tmp_path / "piece_key.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\key g \\major" in text


def test_export_lilypond_respects_timesigstyle_display_intent(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])], time_sig="C")
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "time_style.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "timesigstyle": "numeric"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\numericTimeSignature" in text
    assert "\\time 4/4" in text

    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "timesigstyle": "symbol"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\defaultTimeSignature" in text
