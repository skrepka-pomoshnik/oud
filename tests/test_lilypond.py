from core.model import Bar, Chord, Note, Piece
from exports.lilypond import export_lilypond


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
