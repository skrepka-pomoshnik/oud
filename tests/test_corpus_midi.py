import hashlib
import json
from fractions import Fraction
from pathlib import Path

from oud.exports.midi import export_midi
from petrucci.core.model import Bar, Chord, Note, Piece
from scripts.corpus.midi.__main__ import expected_checksums
from scripts.corpus.midi.audit import audit_corpus, compare_notes
from scripts.corpus.midi.format import MidiNote, MidiNotes, read_midi_notes
from scripts.corpus.midi.references import (
    companion_midi_url,
    fetch_reference,
    generated_cache_path,
    reference_cache_path,
)


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


SOURCE_URL = "https://browse.lutemusic.org/composers/Dowland/fancy.ft3"
REFERENCE_BYTES = b"MThd-not-a-real-midi"


def _cached_reference(cache: Path, payload: bytes = REFERENCE_BYTES) -> Path:
    path = reference_cache_path(cache / "reference", SOURCE_URL)
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    return path


def test_a_cached_reference_reports_its_checksum(tmp_path: Path) -> None:
    path = _cached_reference(tmp_path)

    fetched = fetch_reference(SOURCE_URL, tmp_path / "reference")

    assert fetched.status == "cached"
    assert fetched.sha256 == hashlib.sha256(REFERENCE_BYTES).hexdigest()
    assert fetched.path == path


def test_a_matching_checksum_lets_the_audit_go_on(tmp_path: Path) -> None:
    _cached_reference(tmp_path)
    expected = {SOURCE_URL: hashlib.sha256(REFERENCE_BYTES).hexdigest()}

    (record,) = audit_corpus([(SOURCE_URL, tmp_path / "absent.ft3")], tmp_path, jobs=1, expected=expected)

    assert record.status == "ft3_missing"
    assert record.reference_sha256 == expected[SOURCE_URL]


def test_an_altered_reference_is_reported_stale_before_any_comparison(tmp_path: Path) -> None:
    path = _cached_reference(tmp_path)
    expected = {SOURCE_URL: hashlib.sha256(REFERENCE_BYTES).hexdigest()}
    path.write_bytes(REFERENCE_BYTES + b"!")

    (record,) = audit_corpus([(SOURCE_URL, tmp_path / "absent.ft3")], tmp_path, jobs=1, expected=expected)

    assert record.status == "reference_stale"
    assert record.detail == f"stale companion MIDI: {path}"
    assert record.reference_sha256 == hashlib.sha256(REFERENCE_BYTES + b"!").hexdigest()


def test_the_report_of_an_earlier_run_supplies_the_expected_checksums(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            [{"source_url": SOURCE_URL, "reference_sha256": "abc"}, {"source_url": "x", "reference_sha256": None}]
        ),
        encoding="utf-8",
    )

    assert expected_checksums(report) == {SOURCE_URL: "abc"}
