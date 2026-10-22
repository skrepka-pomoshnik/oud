"""Source course choices survive export even when pitches are interchangeable."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from oud.exports.lilypond import lilypond_text
from petrucci.core.model import Bar, Chord, Note, Piece

TUNING = "g2c3f3a3d4g4"


@pytest.mark.parametrize("profile", ("classic", "petrucci", "gerbode"))
def test_equal_pitches_keep_their_distinct_source_courses(profile: str) -> None:
    piece = Piece(
        title="Course registration",
        strings=6,
        tuning=TUNING,
        bars=[
            Bar(
                chords=[
                    Chord(4, False, None, [Note(1, 0, 0)]),
                    Chord(4, False, None, [Note(2, 5, 0)]),
                ]
            )
        ],
    )

    source = lilypond_text(piece, {}, {}, 12, settings={"style": "french", "tuning": TUNING, "lyprofile": profile})

    assert re.search(r"g'[0-9]+\\1(?:\s|$)", source)
    assert re.search(r"g'[0-9]+\\2(?:\s|$)", source)


def test_chord_unisons_keep_each_course_and_fingering() -> None:
    piece = Piece(
        title="Unison courses",
        strings=6,
        tuning=TUNING,
        bars=[Bar(chords=[Chord(4, False, None, [Note(1, 0, 0), Note(2, 5, 0, left_fingering="4")])])],
    )
    source = lilypond_text(
        piece,
        {},
        {},
        12,
        settings={
            "style": "french",
            "tuning": TUNING,
            "tabnotation": "full",
            "showfingerings": "on",
            "ft3fingering": "left",
        },
    )

    assert "<g'\\1 g'\\2-4>" in source


def test_grid_notes_keep_course_positions() -> None:
    piece = Piece(title="Grid courses", strings=6, bars=[Bar()])
    source = lilypond_text(piece, {(0, 1, 0): "f"}, {}, 12, settings={"style": "french", "tuning": TUNING})

    assert re.search(r"g'[0-9]+\\2(?:\s|$)", source)


def test_retuned_export_keeps_the_existing_pitch_reassignment_contract() -> None:
    piece = Piece(
        title="Retuned",
        strings=6,
        tuning=TUNING,
        bars=[Bar(chords=[Chord(4, False, None, [Note(1, 0, 0)])])],
    )
    source = lilypond_text(piece, {}, {}, 12, settings={"style": "french", "tuning": "a2d3g3b3e4a4"})

    assert re.search(r"\n  g'[0-9]+\s", source)
    assert not re.search(r"g'[0-9]+\\1", source)


def test_default_french_fret_labels_include_the_preserved_high_frets() -> None:
    piece = Piece(
        title="High frets",
        strings=6,
        tuning=TUNING,
        bars=[Bar(chords=[Chord(4, False, None, [Note(1, 14, 0)])])],
    )
    source = lilypond_text(piece, {}, {}, 12, settings={"style": "french", "tuning": TUNING})

    assert '"m" "n" "o" "p"' in source
    assert re.search(r"a''[0-9]+\\1(?:\s|$)", source)


@pytest.mark.parametrize(("binary", "version"), (("lilypond-2.26", "2.26"), ("lilypond", "2.24")))
def test_explicit_courses_unisons_and_fingerings_compile_without_warnings(
    tmp_path: Path,
    binary: str,
    version: str,
) -> None:
    executable = shutil.which(binary)
    if executable is None:
        pytest.skip(f"{binary} is not installed")
    piece = Piece(
        title="Course proof",
        strings=8,
        tuning="e2f2" + TUNING,
        bars=[
            Bar(
                chords=[
                    Chord(4, False, None, [Note(1, 0, 0), Note(2, 5, 0, left_fingering="4")]),
                    Chord(4, False, None, [Note(2, 5, 0, right_fingering="2")]),
                    Chord(4, False, None, [Note(7, 0, 0), Note(1, 14, 0)]),
                    Chord(4, False, None, [Note(8, 0, 0)]),
                ]
            )
        ],
    )
    source = tmp_path / "courses.ly"
    source.write_text(
        lilypond_text(
            piece,
            {},
            {},
            12,
            settings={
                "tuning": piece.tuning or TUNING,
                "style": "french",
                "lyprofile": "gerbode",
                "lilypondversion": version,
                "tabnotation": "full",
                "lytabrhythm": "full",
                "showfingerings": "on",
                "ft3fingering": "both",
            },
        ),
        encoding="utf-8",
    )

    result = subprocess.run(  # noqa: S603 - trusted executable and argument list, no shell
        [executable, "-dno-print-pages", "-o", str(tmp_path / "courses"), str(source)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "warning:" not in result.stderr.lower(), result.stderr
