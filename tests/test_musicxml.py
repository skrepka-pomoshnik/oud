import zipfile

from oud.editor.services.io.loading import load_piece_data
from oud.exports.musicxml import export_musicxml, export_mxl
from oud.importers.musicxml import load_musicxml, load_mxl
from petrucci.core.model import Bar, Chord, Note, Piece


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


def test_export_musicxml_signs_fingering_pluck_dynamic_fermata(tmp_path) -> None:
    bar = Bar(
        chords=[
            Chord(
                note_type=4,
                dotted=False,
                grid=None,
                notes=[
                    Note(1, 1, 0, left_fingering="4", right_fingering="thumb", arpeggio="single"),
                    Note(2, 3, 0, left_fingering="2", right_fingering="2"),
                ],
            ),
        ],
    )
    bar.dynamic = "mf"
    bar.fermata = True
    piece = Piece(title="Signs", bars=[bar], strings=6)
    path = tmp_path / "signs.musicxml"
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
    assert "<dynamics>" in text
    assert "<mf />" in text
    assert "<fermata>normal</fermata>" in text
    assert "<arpeggiate" in text
    assert "<fingering>4</fingering>" in text
    assert "<fingering>2</fingering>" in text
    assert "<pluck>p</pluck>" in text
    assert "<pluck>2</pluck>" in text


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


def test_export_musicxml_time_symbols_and_repeat_direction_symbols(tmp_path) -> None:
    bars = [
        Bar(
            time_sig="C",
            repeat="DS al Coda",
            chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
        ),
        Bar(
            time_sig="C|",
            repeat="To Coda",
            chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 2, 0)])],
        ),
    ]
    piece = Piece(title="Symbols", bars=bars, strings=6)
    path = tmp_path / "symbols.musicxml"
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
    assert '<time symbol="common">' in text
    assert '<time symbol="cut">' in text
    assert "<segno />" in text
    assert "<coda />" in text
    assert "<words>D.S. al Coda</words>" in text
    assert "<words>To Coda</words>" in text


def test_musicxml_import_roundtrip_basic(tmp_path) -> None:
    piece = Piece(
        title="ImportRT",
        composer="Composer",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=6, dotted=True, grid=None, notes=[Note(2, 2, 0)]),
                ],
            ),
            Bar(
                chords=[Chord(note_type=5, dotted=False, grid=None, notes=[])],
            ),
        ],
        strings=6,
    )
    xml_path = tmp_path / "round.musicxml"
    export_musicxml(
        str(xml_path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french"},
        dotted=set(),
    )
    loaded = load_musicxml(str(xml_path))
    assert loaded.title == "ImportRT"
    assert loaded.composer == "Composer"
    assert len(loaded.bars) == 2
    assert loaded.bars[0].chords[0].notes[0].string == 1
    assert loaded.bars[0].chords[1].dotted is True
    assert loaded.bars[1].chords[0].notes == []


def test_mxl_import_roundtrip_basic(tmp_path) -> None:
    piece = Piece(
        title="MXLRT",
        bars=[Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 4, 0)])])],
        strings=6,
    )
    mxl_path = tmp_path / "round.mxl"
    export_mxl(
        str(mxl_path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french"},
        dotted=set(),
    )
    loaded = load_mxl(str(mxl_path))
    assert loaded.title == "MXLRT"
    assert len(loaded.bars) == 1
    assert loaded.bars[0].chords[0].notes[0].string == 3
    assert loaded.bars[0].chords[0].notes[0].fret == 4


def test_load_piece_data_accepts_musicxml_and_mxl(tmp_path) -> None:
    piece = Piece(
        title="Loader",
        bars=[Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)])])],
        strings=6,
    )
    xml_path = tmp_path / "loader.xml"
    mxl_path = tmp_path / "loader.mxl"
    export_musicxml(
        str(xml_path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french"},
        dotted=set(),
    )
    export_mxl(
        str(mxl_path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"tuning": "g2c3f3a3d4g4", "style": "french"},
        dotted=set(),
    )
    xml_piece, *_ = load_piece_data(str(xml_path))
    mxl_piece, *_ = load_piece_data(str(mxl_path))
    assert xml_piece.title == "Loader"
    assert mxl_piece.title == "Loader"
