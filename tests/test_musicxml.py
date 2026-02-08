import zipfile

from oud.core.model import Bar, Chord, Note, Piece
from oud.exports.musicxml import export_musicxml, export_mxl


def test_export_musicxml_writes_core_structure(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    piece = Piece(title="T", composer="C", bars=[bar], strings=6)
    path = tmp_path / "out.musicxml"
    msg = export_musicxml(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4", "time": "3/4", "style": "french"},
        dotted=set(),
    )
    assert "Wrote" in msg
    text = path.read_text(encoding="utf-8")
    assert "<score-partwise" in text
    assert "<part-list>" in text
    assert "<staff-details" in text
    assert 'show-frets="letters"' in text
    assert "<time>" in text
    assert "<beats>3</beats>" in text
    assert "<beat-type>4</beat-type>" in text


def test_export_musicxml_notes_and_repeats(tmp_path) -> None:
    bar1 = Bar(chords=[Chord(note_type=6, dotted=True, grid=None, notes=[Note(1, 0, 0), Note(2, 2, 0)])])
    bar1.repeat = ".:"
    bar2 = Bar(chords=[Chord(note_type=5, dotted=False, grid=None, notes=[])])
    bar2.repeat = ":."
    piece = Piece(title="R", bars=[bar1, bar2], strings=6)
    path = tmp_path / "repeat.xml"
    export_musicxml(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french"},
        dotted=set(),
    )
    text = path.read_text(encoding="utf-8")
    assert "<chord />" in text
    assert "<dot />" in text
    assert "<technical>" in text
    assert "<string>1</string>" in text
    assert "<fret>0</fret>" in text
    assert "<rest />" in text
    assert '<repeat direction="forward"' in text
    assert '<repeat direction="backward"' in text


def test_export_musicxml_repeat_words_and_mxl_package(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    bar.repeat = "DC al Fine"
    piece = Piece(title="W", bars=[bar], strings=6)
    xml_path = tmp_path / "words.musicxml"
    export_musicxml(
        str(xml_path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french"},
        dotted=set(),
    )
    xml_text = xml_path.read_text(encoding="utf-8")
    assert "<words>D.C. al Fine</words>" in xml_text

    mxl_path = tmp_path / "words.mxl"
    msg = export_mxl(
        str(mxl_path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french"},
        dotted=set(),
    )
    assert "Wrote" in msg
    with zipfile.ZipFile(mxl_path) as zf:
        names = set(zf.namelist())
        assert "mimetype" in names
        assert "META-INF/container.xml" in names
        assert any(name.endswith(".xml") for name in names)
