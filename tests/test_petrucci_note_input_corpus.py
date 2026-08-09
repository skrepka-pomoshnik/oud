from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from oud.importers.ft3 import load_ft3
from petrucci import (
    AddLyric,
    AddSlur,
    AddTie,
    EnterNote,
    EnterRest,
    EventInputStyle,
    EventKind,
    NotatedDuration,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    NoteInputOperation,
    NoteInputTransaction,
    Piece,
    PieceAdapterError,
    ScorePosition,
    SpanKind,
    apply_note_input,
    duration_notation,
    notation_score_from_piece,
    pitch_from_midi,
)
from petrucci.core.music.tuning import parse_tuning_pitches, tuning_preset
from scripts.corpus.fetch import load_manifest, manifest_paths

MANIFEST = Path("tests/fixtures/ft3/manifests/ft3-note-input-100.json")
PREVIOUS_MANIFESTS = (
    Path("tests/fixtures/ft3/manifests/ft3-regression.json"),
    Path("tests/fixtures/ft3/manifests/ft3-random-75.json"),
    Path("tests/fixtures/ft3/manifests/ft3-random-75-v2.json"),
    Path("tests/fixtures/ft3/manifests/ft3-random-50-v3.json"),
    Path("tests/fixtures/ft3/manifests/ft3-random-63-v4.json"),
    Path("tests/fixtures/ft3/manifests/ft3-random-37-v5.json"),
)
NOTE_TYPE_DENOMINATORS = {2: 1, 3: 2, 4: 4, 5: 8, 6: 16, 7: 32, 8: 64}


@pytest.fixture(scope="module")
def corpus_pieces() -> list[tuple[dict[str, object], Path, Piece]]:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = load_manifest(MANIFEST)
    paths = manifest_paths(manifest)
    if any(not path.is_file() for path in paths):
        pytest.skip(f"fetch {MANIFEST} before running external note-input acceptance")
    return [(entry, path, load_ft3(str(path))) for entry, path in zip(raw["files"], paths, strict=True)]


def test_note_input_manifest_is_fixed_and_disjoint_from_previous_corpora() -> None:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = load_manifest(MANIFEST)
    previous = [entry for path in PREVIOUS_MANIFESTS for entry in load_manifest(path).files]

    assert raw["selection"]["selected"] == 100
    assert raw["selection"]["seed"] == 20260804
    assert "one-time" in raw["selection"]["method"]
    assert "never repeated" in raw["selection"]["method"]
    assert len(manifest.files) == 100
    assert len({entry.path for entry in manifest.files}) == 100
    assert len({entry.url for entry in manifest.files}) == 100
    assert len({entry.sha256 for entry in manifest.files}) == 100
    assert {entry.url for entry in manifest.files}.isdisjoint(entry.url for entry in previous)
    assert {entry.sha256 for entry in manifest.files}.isdisjoint(entry.sha256 for entry in previous)


def test_note_input_manifest_expectations_match_verified_payloads(
    corpus_pieces: list[tuple[dict[str, object], Path, Piece]],
) -> None:
    for expected, path, piece in corpus_pieces:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected["sha256"]
        assert len(piece.bars) == expected["bars"]
        assert piece.strings == expected["strings"]
        assert piece.style == expected["style"]
        assert sum(len(bar.chords) for bar in piece.bars) == expected["tab_chords"]
        score = _canonical_score(piece)
        assert (len(score.staffs) if score else 0) == expected["note_staffs"]
        assert _event_count(score) == expected["notation_events"]
        assert (sum(len(staff.lyrics) for staff in score.staffs) if score else 0) == expected["lyrics"]


def test_public_note_input_reconstructs_all_100_new_gerbode_scores(
    corpus_pieces: list[tuple[dict[str, object], Path, Piece]],
) -> None:
    canonical_count = 0
    tab_event_count = 0
    for index, (_expected, _path, piece) in enumerate(corpus_pieces, start=1):
        canonical = _canonical_score(piece)
        if canonical is not None:
            assert _replay_canonical_score(canonical) == canonical
            canonical_count += 1
            continue
        expected, operations = _tab_note_sequence(piece, score_index=index)
        entered = apply_note_input(_empty_score_content(expected), NoteInputTransaction(tuple(operations)))
        assert entered.score == expected
        tab_event_count += _event_count(expected)

    assert canonical_count == 7
    assert tab_event_count >= 20_000


def _canonical_score(piece: Piece) -> NotationScore | None:
    try:
        return notation_score_from_piece(piece)
    except PieceAdapterError:
        return None


def _event_count(score: NotationScore | None) -> int:
    if score is None:
        return 0
    return sum(len(measure.events) for staff in score.staffs for measure in staff.measures)


def _empty_score_content(score: NotationScore) -> NotationScore:
    staffs = tuple(
        replace(
            staff,
            measures=tuple(replace(measure, events=()) for measure in staff.measures),
            lyrics=(),
            spans=(),
        )
        for staff in score.staffs
    )
    return replace(score, staffs=staffs)


def _replay_canonical_score(score: NotationScore) -> NotationScore:
    operations: list[NoteInputOperation] = []
    for staff in score.staffs:
        for measure in staff.measures:
            for event in measure.events:
                operations.extend(_event_operations(staff.id, measure.id, event))
        operations.extend(
            AddLyric(
                lyric.event_id,
                lyric.text,
                lyric.verse,
                lyric.syllabic,
                lyric.extender,
                lyric.id,
            )
            for lyric in staff.lyrics
        )
        operations.extend(
            (AddTie if span.kind is SpanKind.TIE else AddSlur)(
                span.start_event_id,
                span.end_event_id,
                span.id,
            )
            for span in staff.spans
        )
    return apply_note_input(_empty_score_content(score), NoteInputTransaction(tuple(operations))).score


def _event_operations(staff_id: str, measure_id: str, event: NotationEvent) -> list[NoteInputOperation]:
    position = ScorePosition(staff_id, measure_id, event.onset, event.voice)
    duration = _notated_duration(event)
    style = EventInputStyle(
        stem=event.stem,
        beam=event.beam,
        fermata=event.fermata,
        dynamic=event.dynamic,
        ornament=event.ornament,
        editorial_brackets=event.editorial_brackets,
        grace=event.grace,
    )
    if event.kind is EventKind.REST:
        return [EnterRest(position, duration, event.id, style=style)]
    operations: list[NoteInputOperation] = [
        EnterNote(position, event.pitches[0], duration, event.id, style=style),
    ]
    operations.extend(EnterNote(position, pitch, chord=True) for pitch in event.pitches[1:])
    return operations


def _notated_duration(event: NotationEvent) -> NotatedDuration:
    written = event.duration
    if event.tuplet is not None:
        written *= Fraction(event.tuplet.actual, event.tuplet.normal)
    notation = duration_notation(written)
    assert notation is not None, f"event {event.id} has an unsupported written duration {written}"
    denominator, dots = notation
    return NotatedDuration(
        denominator,
        dots,
        event.tuplet.actual if event.tuplet else None,
        event.tuplet.normal if event.tuplet else None,
    )


def _tab_note_sequence(piece: Piece, *, score_index: int) -> tuple[NotationScore, list[NoteInputOperation]]:
    score_id = f"tab-score-{score_index}"
    staff_id = f"{score_id}:staff"
    tuning = piece.tuning or tuning_preset(f"renaissance{piece.strings}")
    assert tuning is not None
    string_pitches = parse_tuning_pitches(tuning)
    measures: list[NotationMeasure] = []
    operations: list[NoteInputOperation] = []
    for bar_index, bar in enumerate(piece.bars):
        measure_id = f"{staff_id}:measure-{bar_index}"
        events: list[NotationEvent] = []
        onset = Fraction()
        for chord_index, chord in enumerate(bar.chords):
            duration = NotatedDuration(NOTE_TYPE_DENOMINATORS[chord.note_type], dots=int(chord.dotted))
            pitches = tuple(
                dict.fromkeys(pitch_from_midi(string_pitches[note.string - 1] + note.fret) for note in chord.notes),
            )
            event_id = f"{measure_id}:event-{chord_index}"
            event = NotationEvent(event_id, onset, duration.duration, EventKind.NOTE, pitches)
            events.append(event)
            operations.extend(_event_operations(staff_id, measure_id, event))
            onset += duration.duration
        measures.append(NotationMeasure(measure_id, bar_index + 1, tuple(events), irregular=True))
    score = NotationScore(score_id, (NotationStaff(staff_id, tuple(measures)),))
    return score, operations
