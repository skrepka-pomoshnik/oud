from oud.core.model import Bar, Chord, Note, Piece
from oud.exports.lilypond import export_lilypond


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
