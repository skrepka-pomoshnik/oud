"""Executable fixtures shared by Petrucci proof and LilyPond export tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from petrucci.core.model import Bar, Chord, LyricEvent, MelodyEvent, Note, Piece
from petrucci.core.score import (
    AccidentalDisplay,
    BarlineKind,
    EventKind,
    KeySignature,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    OrnamentKind,
    PitchStep,
    SpanKind,
    StemDirection,
    TimeSignature,
    WrittenPitch,
    pitch_from_midi,
)
from petrucci.engraving.layout.engine import ScoreLayout, layout_collisions

MATRIX_PATH = Path("tests/fixtures/ft3/manifests/engraving-quality-matrix.json")
Position = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class MatrixFixture:
    """One source-independent proof score and its LilyPond export input."""

    score: NotationScore
    piece: Piece
    settings: dict[str, str]
    overrides: dict[Position, str]
    durations: dict[Position, int]
    slurs: list[Position]
    ties: list[Position]


def load_quality_matrix() -> dict[str, Any]:
    """Load the checked-in engraving contract inventory."""

    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _event(
    event_id: str,
    onset: int,
    midi: int,
    *,
    voice: int = 0,
    **options: Any,
) -> NotationEvent:
    return NotationEvent(
        id=event_id,
        onset=Fraction(onset, 4),
        duration=Fraction(1, 4),
        kind=EventKind.NOTE,
        pitches=(pitch_from_midi(midi),),
        voice=voice,
        **options,
    )


def _piece_with_tab(
    *,
    repeat: str | None = None,
    ending_numbers: tuple[int, ...] = (),
    fermata: bool = False,
    time_sig: str | None = None,
) -> Piece:
    chord = Chord(
        note_type=4,
        dotted=False,
        grid=None,
        notes=[Note(1, 0, 0), Note(2, 2, 0)],
    )
    return Piece(
        title="Matrix proof",
        bars=[Bar(chords=[chord], repeat=repeat, ending_numbers=ending_numbers, fermata=fermata, time_sig=time_sig)],
        strings=6,
    )


def _tab_fixture() -> MatrixFixture:
    events = (_event("tab-1", 0, 60), _event("tab-2", 1, 62))
    score = NotationScore(
        id="tab-registration",
        staffs=(
            NotationStaff(
                id="tab-staff",
                label="Lute",
                measures=(NotationMeasure("tab-measure", 1, events, time_signature=TimeSignature(2, 4)),),
            ),
        ),
    )
    piece = _piece_with_tab()
    return MatrixFixture(score, piece, {}, {}, {}, [], [])


def _voice_lute_fixture(stanzas: int = 1) -> MatrixFixture:
    voice_events = (_event("voice-1", 0, 60), _event("voice-2", 1, 62))
    lute_events = (_event("lute-1", 0, 48), _event("lute-2", 1, 50))
    lyrics = tuple(
        LyricSyllable(f"lyric-{index}", event.id, text)
        for index, (event, text) in enumerate(zip(voice_events, ("la", "mi"), strict=True))
    )
    score = NotationScore(
        id="voice-lute-registration",
        staffs=(
            NotationStaff(
                id="voice-staff",
                label="Voice",
                measures=(NotationMeasure("voice-measure", 1, voice_events, time_signature=TimeSignature(3, 4)),),
                lyrics=lyrics,
            ),
            NotationStaff(
                id="lute-staff",
                label="Lute",
                measures=(NotationMeasure("lute-measure", 1, lute_events, time_signature=TimeSignature(3, 4)),),
            ),
        ),
    )
    bar = Bar(
        chords=[Chord(4, False, None, [Note(1, 0, 0)]), Chord(4, False, None, [Note(1, 2, 0)])],
        melody_events=[MelodyEvent("c", 0, note_type=4), MelodyEvent("d", 1, note_type=4)],
        lyric_event_rows=[[LyricEvent("la", 0), LyricEvent("mi", 1)] for _ in range(stanzas)],
        time_sig="3/4",
    )
    settings = {"showmelody": "on", "showlyrics": "on", "vocalpos": "top", "lyricmode": "all"}
    return MatrixFixture(score, Piece(title="Voice and lute", bars=[bar], strings=6), settings, {}, {}, [], [])


def _polyphonic_fixture() -> MatrixFixture:
    events = (
        _event("poly-low", 0, 60, voice=0),
        NotationEvent(
            id="poly-high",
            onset=Fraction(0),
            duration=Fraction(1, 4),
            kind=EventKind.NOTE,
            pitches=(WrittenPitch(PitchStep.F, 4, 1, AccidentalDisplay.EXPLICIT),),
            voice=1,
            stem=StemDirection.UP,
        ),
    )
    score = NotationScore(
        id="polyphonic-collision",
        staffs=(
            NotationStaff(
                id="poly-staff",
                label="Lute",
                measures=(NotationMeasure("poly-measure", 1, events, time_signature=TimeSignature(2, 4)),),
            ),
        ),
    )
    return MatrixFixture(score, _piece_with_tab(), {}, {}, {}, [], [])


def _broken_spans_fixture() -> MatrixFixture:
    first = _event("span-start", 0, 60)
    second = _event("span-end", 0, 62)
    score = NotationScore(
        id="broken-spans",
        staffs=(
            NotationStaff(
                id="span-staff",
                label="Voice",
                measures=(
                    NotationMeasure(
                        "span-measure-1", 1, (first,), time_signature=TimeSignature(), forced_break_after=True
                    ),
                    NotationMeasure("span-measure-2", 2, (second,)),
                ),
                spans=(
                    NotationSpan("tie-1", SpanKind.TIE, first.id, second.id),
                    NotationSpan("slur-1", SpanKind.SLUR, first.id, second.id),
                ),
            ),
        ),
    )
    piece = Piece(title="Broken spans", bars=[Bar(), Bar()], strings=6)
    return MatrixFixture(
        score,
        piece,
        {},
        {(0, 0, 0): "a", (0, 0, 2): "b"},
        {(0, 0, 0): 4, (0, 0, 2): 4},
        [(0, 0, 2)],
        [(0, 2, 2)],
    )


def _repeat_fixture() -> MatrixFixture:
    event = _event("repeat-event", 0, 60, fermata=True, ornament=OrnamentKind.PLUS)
    score = NotationScore(
        id="repeat-volta",
        staffs=(
            NotationStaff(
                id="repeat-staff",
                label="Lute",
                measures=(
                    NotationMeasure(
                        "repeat-measure",
                        1,
                        (event,),
                        time_signature=TimeSignature(),
                        barline=BarlineKind.REPEAT_BOTH,
                        ending_numbers=(1,),
                    ),
                ),
            ),
        ),
    )
    piece = _piece_with_tab(repeat=":|:", ending_numbers=(1,))
    return MatrixFixture(score, piece, {}, {}, {}, [], [])


def _single_measure_fixture(
    score_id: str,
    piece: Piece,
    *,
    settings: dict[str, str] | None = None,
    **measure_options: Any,
) -> MatrixFixture:
    events = measure_options.pop("events", (_event(f"{score_id}-1", 0, 60), _event(f"{score_id}-2", 1, 62)))
    measure = NotationMeasure(f"{score_id}-measure", 1, events, **measure_options)
    score = NotationScore(
        id=score_id, staffs=(NotationStaff(id=f"{score_id}-staff", label="Lute", measures=(measure,)),)
    )
    return MatrixFixture(score, piece, settings or {}, {}, {}, [], [])


def _fermata_fixture() -> MatrixFixture:
    events = (_event("fermata-1", 0, 60, fermata=True), _event("fermata-2", 1, 62))
    return _single_measure_fixture(
        "fermata", _piece_with_tab(fermata=True), events=events, time_signature=TimeSignature(2, 4)
    )


def _cut_time_fixture() -> MatrixFixture:
    return _single_measure_fixture("cut-time", _piece_with_tab(time_sig="C|"), time_signature=TimeSignature(2, 2))


def _key_signature_fixture() -> MatrixFixture:
    return _single_measure_fixture(
        "key-signature",
        _piece_with_tab(),
        settings={"key": "G"},
        time_signature=TimeSignature(2, 4),
        key_signature=KeySignature(1),
    )


_FIXTURE_BUILDERS: dict[str, Callable[[], MatrixFixture]] = {
    "fermata": _fermata_fixture,
    "cut-time": _cut_time_fixture,
    "key-signature": _key_signature_fixture,
    "tab-registration-and-rhythm": _tab_fixture,
    "voice-lute-lyrics": _voice_lute_fixture,
    "polyphonic-collisions": _polyphonic_fixture,
    "broken-spans": _broken_spans_fixture,
    "repeat-and-volta-registration": _repeat_fixture,
    "gerbode-multiverse-registration": lambda: _voice_lute_fixture(12),
}


def fixture_for(case_id: str) -> MatrixFixture:
    """Return the deterministic fixture named by one matrix case."""

    try:
        return _FIXTURE_BUILDERS[case_id]()
    except KeyError as error:
        raise KeyError(case_id) from error


def assert_proof_contract(case: dict[str, Any], fixture: MatrixFixture, layout: ScoreLayout) -> None:
    """Assert the matrix's structural and collision contract for a proof layout."""

    proof = case["proof"]
    assert len(layout.event_ids) >= proof["min_events"]
    assert len(fixture.score.staffs) >= proof["min_staffs"]
    roles = {element.key.role.value for element in layout.elements}
    assert set(proof["required_roles"]).issubset(roles)
    assert len(layout_collisions(layout)) <= proof["max_collisions"]


def assert_lilypond_contract(case: dict[str, Any], text: str) -> None:
    """Assert export tokens declared by one shared matrix case."""

    for token in case["lilypond"]["contains"]:
        assert token in text
