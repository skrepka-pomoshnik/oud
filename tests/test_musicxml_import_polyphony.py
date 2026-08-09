from pathlib import Path

from oud.importers.musicxml import load_musicxml


def test_musicxml_import_registers_parallel_tablature_voices(tmp_path: Path) -> None:
    source = tmp_path / "polyphonic.musicxml"
    source.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list><score-part id="P1"><part-name>Lute</part-name></score-part></part-list>
  <part id="P1"><measure number="1">
    <attributes><divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note><pitch><step>C</step><octave>4</octave></pitch><duration>8</duration><voice>1</voice>
      <notations><technical><string>1</string><fret>0</fret></technical></notations></note>
    <note><pitch><step>D</step><octave>4</octave></pitch><duration>8</duration><voice>1</voice>
      <notations><technical><string>1</string><fret>2</fret></technical></notations></note>
    <backup><duration>16</duration></backup>
    <note><pitch><step>G</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice>
      <notations><technical><string>4</string><fret>0</fret></technical></notations></note>
  </measure></part>
</score-partwise>
""",
        encoding="utf-8",
    )

    piece = load_musicxml(str(source))

    assert len(piece.bars[0].chords) == 2
    assert [(note.string, note.fret) for note in piece.bars[0].chords[0].notes] == [(1, 0), (4, 0)]
    assert [(note.string, note.fret) for note in piece.bars[0].chords[1].notes] == [(1, 2)]
    assert [chord.note_type for chord in piece.bars[0].chords] == [3, 3]
