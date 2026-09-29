"""Tuplets in melody events export as LilyPond tuplets, not as scaled durations (TODO S32)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from oud.exports.lilypond import export_lilypond
from oud.exports.lilypond.timing import timed_items_duration
from oud.settings import DEFAULT_SETTINGS
from petrucci.core.model import (
    Bar,
    Chord,
    ImportedBarContent,
    ImportedScore,
    ImportedStaff,
    MelodyEvent,
    Note,
    Piece,
)


def _triplet(index: int, pitch: str = "c") -> MelodyEvent:
    return MelodyEvent(pitch, index, note_type=5, tuplet_actual=3, tuplet_normal=2)


def _export(tmp_path: Path, events: list[MelodyEvent], time_sig: str = "2/4") -> list[str]:
    """Export an imported score whose notation staff holds ``events`` in one bar."""

    staff = ImportedStaff(
        kind="note", label="Voice", bars=[ImportedBarContent(0, melody_events=events, time_sig=time_sig)]
    )
    piece = Piece(
        title="T",
        bars=[Bar(chords=[Chord(4, False, None, [Note(1, 0, 0)]) for _ in range(2)], time_sig=time_sig)],
        strings=6,
    )
    piece.imported_score = ImportedScore("ft3", [staff])
    target = tmp_path / "score.ly"
    export_lilypond(str(target), piece, {}, {}, 12, settings={**DEFAULT_SETTINGS, "showmelody": "on"})
    return [line.strip() for line in target.read_text(encoding="utf-8").splitlines()]


def test_a_triplet_is_written_as_a_tuplet_block(tmp_path: Path) -> None:
    lines = _export(tmp_path, [_triplet(0), _triplet(1), _triplet(2), MelodyEvent("d", 3, note_type=4)])

    assert "\\tuplet 3/2 {" in lines
    block = lines.index("\\tuplet 3/2 {")
    assert lines[block + 1 : block + 5] == ["c'8", "c'8", "c'8", "}"]
    assert lines[block + 5] == "d'4"
    assert not any("scaleDurations" in line for line in lines)


def test_two_adjacent_triplets_are_two_blocks(tmp_path: Path) -> None:
    events = [_triplet(index) for index in range(6)]
    lines = _export(tmp_path, events, time_sig="2/4")

    assert lines.count("\\tuplet 3/2 {") == 2
    assert lines.count("}") >= 2


def test_a_bar_without_tuplets_is_unchanged(tmp_path: Path) -> None:
    events = [MelodyEvent("c", 0, note_type=4), MelodyEvent("d", 1, note_type=4)]
    lines = _export(tmp_path, events)

    assert not any("tuplet" in line for line in lines)
    assert "c'4" in lines
    assert "d'4" in lines


def test_a_tuplet_event_counts_its_written_value_times_the_ratio() -> None:
    events = [_triplet(0), _triplet(1), _triplet(2)]

    assert timed_items_duration(events) == Fraction(1, 4)
    assert timed_items_duration([MelodyEvent("c", 0, note_type=5)]) == Fraction(1, 8)
