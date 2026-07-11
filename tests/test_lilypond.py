import subprocess
from pathlib import Path

import pytest

from oud.core.ft3 import build_durations, load_ft3
from oud.exports import lilypond as lp
from oud.exports.lilypond import export_lilypond
from oud.petrucci.model import (
    Bar,
    Chord,
    ImportedBarContent,
    ImportedScore,
    ImportedStaff,
    LyricEvent,
    MelodyEvent,
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
    assert 'D.C. al Fine' in text


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
    assert 'scripts.ufermata' in text


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
    assert '-4\\rightHandFinger #2' in text or '-4 \\rightHandFinger #2' in text
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


def test_export_lilypond_emits_vocal_staff_and_lyrics_when_enabled(tmp_path) -> None:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 3, 0)]),
        ],
        melody_events=[
            MelodyEvent("d", 0, note_type=4),
            MelodyEvent("a", 1, note_type=4),
            MelodyEvent("d'", 2, note_type=4),
        ],
        lyric_event_rows=[
            [
                LyricEvent("Can", 0, syllabic="single"),
                LyricEvent("she", 1, syllabic="single"),
                LyricEvent("ex-", 2, syllabic="begin"),
            ],
        ],
        time_sig="O",
    )
    piece = Piece(title="Can she excuse?", composer="John Dowland", bars=[bar], strings=6)
    path = tmp_path / "vocal.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g2c3f3a3d4g4",
            "style": "french",
            "showmelody": "on",
            "showlyrics": "on",
            "vocalpos": "top",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "\\new StaffGroup <<" in text
    assert '\\new Staff = "melodyStaff"' in text
    assert '\\new Lyrics \\lyricsto "melodyVoice" {' in text
    assert '"Can" "she" "ex-" --' in text
    assert "\\new TabStaff" in text
    assert "\\time 3/4" in text


def test_export_lilypond_emits_imported_vocal_only_staffgroup(tmp_path) -> None:
    piece = Piece(
        title="Now O now",
        key="GM",
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(
                    kind="note",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=0,
                            time_sig="3/4",
                            melody_events=[
                                MelodyEvent("b", 0, note_type=3),
                                MelodyEvent("a", 1, note_type=4),
                            ],
                        ),
                        ImportedBarContent(
                            source_bar_index=1,
                            melody_events=[
                                MelodyEvent("g", 0, note_type=3),
                                MelodyEvent("f#", 1, note_type=4),
                            ],
                            system_break=True,
                        ),
                    ],
                ),
                ImportedStaff(
                    kind="lyrics",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=0,
                            lyric_event_rows=[[LyricEvent("Now", 0), LyricEvent("O", 1)]],
                        ),
                        ImportedBarContent(
                            source_bar_index=1,
                            lyric_event_rows=[[LyricEvent("now", 0), LyricEvent("I", 1)]],
                        ),
                    ],
                ),
            ],
        ),
    )
    path = tmp_path / "imported_vocal_only.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"showmelody": "on", "showlyrics": "on", "vocalpos": "top"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\new TabStaff" not in text
    assert '\\new Staff = "melodyStaff"' in text
    assert '"Now" "O"' in text
    assert "\\key g \\major" in text
    assert "\\break" in text


def test_export_lilypond_uses_imported_vocal_staff_over_bar_fallback_when_present(tmp_path) -> None:
    piece = Piece(
        title="Mixed",
        bars=[Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])],
        strings=6,
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(
                    kind="note",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=0,
                            melody_events=[
                                MelodyEvent("r", 0, note_type=4, is_rest=True),
                                MelodyEvent("f#", 1, note_type=4),
                            ],
                        ),
                    ],
                ),
                ImportedStaff(
                    kind="lyrics",
                    bars=[ImportedBarContent(source_bar_index=0, lyrics=["Rest sharp"])],
                ),
            ],
        ),
    )
    path = tmp_path / "mixed_imported.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g2c3f3a3d4g4",
            "showmelody": "on",
            "showlyrics": "on",
            "vocalpos": "bottom",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "\\new TabStaff" in text
    assert "  r4" in text
    assert "fis4" in text
    assert '"Rest" "sharp"' in text


def test_export_lilypond_aligns_sparse_imported_lyrics_by_source_bar(tmp_path) -> None:
    piece = Piece(
        title="Sparse imported vocal",
        bars=[Bar(), Bar(), Bar()],
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(
                    kind="note",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=0,
                            melody_events=[MelodyEvent("c", 0, note_type=4)],
                        ),
                        ImportedBarContent(
                            source_bar_index=0,
                            melody_events=[
                                MelodyEvent("b", 0, note_type=4),
                                MelodyEvent("a", 1, note_type=4),
                            ],
                        ),
                        ImportedBarContent(
                            source_bar_index=2,
                            melody_events=[MelodyEvent("g", 0, note_type=4)],
                        ),
                    ],
                ),
                ImportedStaff(
                    kind="lyrics",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=2,
                            lyric_event_rows=[[LyricEvent("late", 0)]],
                        ),
                    ],
                ),
            ],
        ),
    )
    path = tmp_path / "sparse_imported.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"showmelody": "on", "showlyrics": "on"},
    )
    text = path.read_text(encoding="utf-8")
    assert "  c4" not in text
    assert text.count("  b4") == 1
    assert text.count("  a4") == 1
    assert "_ _ _ \"late\"" in text


def test_export_lilypond_emits_barline_only_imported_score(tmp_path) -> None:
    piece = Piece(
        title="Barlines",
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(
                    kind="barline",
                    bars=[
                        ImportedBarContent(source_bar_index=0, repeat=".:", time_sig="3/4"),
                        ImportedBarContent(
                            source_bar_index=1,
                            barline="||",
                            system_break=True,
                        ),
                    ],
                ),
            ],
        ),
    )
    path = tmp_path / "barline_only.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"showmelody": "on"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\new TabStaff" not in text
    assert text.count("  r4") == 2
    assert '\\bar ".|:"' in text
    assert '\\bar "||"' in text
    assert "\\break" in text


def test_export_lilypond_preserves_ft3_tab_system_break(tmp_path) -> None:
    piece = Piece(
        title="Break",
        bars=[
            Bar(
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
                system_break=True,
            ),
        ],
        strings=6,
    )
    path = tmp_path / "tab_break.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4"},
    )
    assert "\\break" in path.read_text(encoding="utf-8")


def test_export_lilypond_respects_vocalpos_bottom_order(tmp_path) -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
        melody_events=[MelodyEvent("d", 0, note_type=4)],
        lyric_event_rows=[[LyricEvent("Can", 0)]],
    )
    piece = Piece(title="Order", bars=[bar], strings=6)
    path = tmp_path / "vocal_order.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={
            "tuning": "g2c3f3a3d4g4",
            "showmelody": "on",
            "showlyrics": "on",
            "vocalpos": "bottom",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert text.index("\\new TabStaff") < text.index('\\new Staff = "melodyStaff"')


def test_export_lilypond_emits_duet_staffgroup_with_labels(tmp_path) -> None:
    top_bar_1 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])], time_sig="C")
    top_bar_2 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)])])
    bottom_bar_1 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)])])
    bottom_bar_2 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, 3, 0)])])
    piece = Piece(
        title="Duet",
        bars=[top_bar_1, top_bar_2, bottom_bar_1, bottom_bar_2],
        strings=6,
        part="score",
        ensemble="lute 1: prime,lute 2: bass",
    )
    path = tmp_path / "duet.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4", "duetscoreview": "both"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\new StaffGroup <<" in text
    assert text.count("\\new TabStaff") == 2
    assert 'instrumentName = "Lute 1"' in text
    assert 'instrumentName = "Lute 2"' in text
    assert text.count("stringTunings = \\stringTuning") == 2


def test_export_lilypond_ft3_meter_mapping_and_midpiece_changes_synthetic(tmp_path) -> None:
    piece = Piece(
        title="Meters",
        strings=6,
        bars=[
            Bar(time_sig="O", chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)])]),
            Bar(time_sig="C|", chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])]),
            Bar(time_sig="6/8", chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 3, 0)])]),
        ],
    )
    path = tmp_path / "meters.ly"
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
    assert "\\time 3/4" in text
    assert "\\time 2/2" in text
    assert "\\time 6/8" in text
    # no duplicate \time for bar 2 with inherited meter
    assert text.count("\\time 3/4") == 1

    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g4d4a3f3c3g2", "timesigstyle": "fraction"},
    )
    text = path.read_text(encoding="utf-8")
    assert "\\numericTimeSignature" in text


def test_export_lilypond_emits_midpiece_time_changes_for_real_ft3_if_available(tmp_path) -> None:
    src = Path("lutemusic/ich_bin_eine_blume_zu_saron_T.ft3")
    if not src.exists():
        pytest.skip("local FT3 corpus file not available")

    piece = load_ft3(str(src))
    path = tmp_path / "ichbin.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations=build_durations(piece),
        bar_width=12,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french", "key": piece.key or "C"},
    )
    text = path.read_text(encoding="utf-8")
    assert text.count("\\time ") >= 3
    assert "\\time 3/4" in text
    assert "\\time 2/2" in text
    assert "\\time 6/8" in text


def test_export_lilypond_keeps_ft3_repeat_barlines_from_real_file_if_available(tmp_path) -> None:
    src = Path("lutemusic/wu_sol_ich_mich_hin_keren.ft3")
    if not src.exists():
        pytest.skip("local FT3 corpus file not available")

    piece = load_ft3(str(src))
    path = tmp_path / "wusol.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations=build_durations(piece),
        bar_width=12,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french", "key": piece.key or "C"},
    )
    text = path.read_text(encoding="utf-8")
    assert '\\bar ".|:"' in text
    assert '\\bar ":|."' in text


@pytest.mark.parametrize(
    ("src_name", "expected_tokens"),
    [
        ("wu_sol_ich_mich_hin_keren.ft3", ('\\bar ".|:"', '\\bar ":|."')),
        ("czarna_krowa.ft3", ('\\bar ".|:"', '\\bar ":|."', '\\bar "||"')),
        ("can_she_excuse.ft3", ('\\bar ".|:"', '\\bar ":|."', '\\bar "||"')),
    ],
)
def test_export_lilypond_real_ft3_repeat_barline_matrix_if_available(
    tmp_path,
    src_name: str,
    expected_tokens: tuple[str, ...],
) -> None:
    src = Path("lutemusic") / src_name
    if not src.exists():
        pytest.skip("local FT3 corpus file not available")
    piece = load_ft3(str(src))
    path = tmp_path / f"{src.stem}.ly"
    export_lilypond(
        str(path),
        piece,
        overrides={},
        durations=build_durations(piece),
        bar_width=12,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french", "key": piece.key or "C"},
    )
    text = path.read_text(encoding="utf-8")
    for token in expected_tokens:
        assert token in text


@pytest.mark.parametrize(
    "src_name",
    [
        "wu_sol_ich_mich_hin_keren.ft3",
        "czarna_krowa.ft3",
        "can_she_excuse.ft3",
        "05_a_fancy.ft3",
        "23a_frogg_galliard_2.ft3",
    ],
)
def test_export_lilypond_real_ft3_smoke_matrix_if_available(tmp_path, src_name: str) -> None:
    src = Path("lutemusic") / src_name
    if not src.exists():
        pytest.skip("local FT3 corpus file not available")
    piece = load_ft3(str(src))
    path = tmp_path / f"{src.stem}.ly"
    msg = export_lilypond(
        str(path),
        piece,
        overrides={},
        durations=build_durations(piece),
        bar_width=12,
        settings={
            "tuning": "g2c3f3a3d4g4",
            "style": "french",
            "key": piece.key or "C",
        },
    )
    assert msg.startswith("Wrote ")
    text = path.read_text(encoding="utf-8")
    assert "\\new TabStaff" in text
    assert "stringTunings" in text
    assert "\\bar " in text
