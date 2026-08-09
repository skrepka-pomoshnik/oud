from fractions import Fraction
from pathlib import Path

from oud.exports.midi import export_midi
from petrucci.core.model import Bar, Chord, Note, Piece
from scripts.corpus.midi.audit import compare_notes
from scripts.corpus.midi.format import MidiNote, MidiNotes, read_midi_notes
from scripts.corpus.midi.references import companion_midi_url, generated_cache_path, reference_cache_path


def test_companion_midi_location_is_derived_from_ft3_source() -> None:
    source = "https://browse.lutemusic.org/composers/Dowland/fancy.ft3"

    assert companion_midi_url(source) == "https://browse.lutemusic.org/composers/Dowland/midi/fancy.mid"
    assert reference_cache_path(Path("cache"), source) == Path(
        "cache/browse.lutemusic.org/composers/Dowland/midi/fancy.mid",
    )
    assert generated_cache_path(Path("cache"), source) == Path(
        "cache/browse.lutemusic.org/composers/Dowland/fancy.mid",
    )


def test_midi_reader_accepts_oud_export(tmp_path: Path) -> None:
    path = tmp_path / "one.mid"
    piece = Piece(bars=[Bar(chords=[Chord(4, False, None, [Note(1, 2, 0)])])])
    export_midi(str(path), piece, {}, {}, 8)

    notes = read_midi_notes(path)

    assert notes.ppq == 480
    assert [(note.channel, note.pitch) for note in notes.notes] == [(0, 69)]


def test_midi_comparison_reports_global_transposition() -> None:
    reference = MidiNotes(384, (MidiNote(Fraction(0), 0, 61), MidiNote(Fraction(1), 0, 64)))
    generated = MidiNotes(480, (MidiNote(Fraction(0), 0, 60), MidiNote(Fraction(1), 0, 63)))

    comparison = compare_notes(reference, generated)

    assert comparison.best_transposition == 1
    assert comparison.onset_similarity == 1.0
    assert comparison.pitch_overlap == 1.0
